# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""
动画修正工具 (参考 SC2ArtTools / M3_Import 移植):
- 帧缩放修正 (Frame Scale Correction): 检测并清除时间分布异常的关键帧
- 关键帧精简 (Keyframe Reduce): 在误差范围内删除冗余关键帧
- 重复关键帧清理: 删除值完全相同的连续关键帧
- F-Curve 诊断: 列出孤立/空 F-Curve
"""

import bpy
import math
from .anim_tools import get_arm_obj, get_selected_pose_bones


# ──────────────────────────────────────────────
# 帧缩放修正 (Frame Scale Correction)
# ──────────────────────────────────────────────

class DH_OT_FrameScaleCorrection(bpy.types.Operator):
    """检测并清除时间分布异常的关键帧，修复动画顿挫感"""
    bl_idname = 'donghua.frame_scale_correction'
    bl_label = '帧缩放修正'
    bl_description = (
        '检测关键帧时间间隔异常（过密或过疏）的区段，'
        '删除分布不均匀的关键帧以平滑动画节奏'
    )
    bl_options = {'UNDO'}

    threshold: bpy.props.FloatProperty(
        name='间隔偏差阈值',
        description='当相邻关键帧间隔与平均间隔的偏差超过此比例时标记为异常',
        default=0.3, min=0.05, max=0.95, subtype='FACTOR',
    )
    selected_only: bpy.props.BoolProperty(
        name='仅选中骨骼',
        description='仅处理选中骨骼的 F-Curve',
        default=True,
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'threshold')
        layout.prop(self, 'selected_only')

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        # 确定要处理的骨骼名
        if self.selected_only:
            bone_names = {pb.name for pb in get_selected_pose_bones(context)}
            if not bone_names:
                self.report({'WARNING'}, '没有选中任何骨骼')
                return {'CANCELLED'}
        else:
            bone_names = None  # 处理所有

        total_removed = 0

        for fc in action.fcurves:
            if 'pose.bones[' not in fc.data_path:
                continue
            try:
                bname = fc.data_path.split('"')[1]
            except IndexError:
                continue
            if bone_names is not None and bname not in bone_names:
                continue

            kps = fc.keyframe_points
            if len(kps) < 3:
                continue

            # 计算平均间隔
            frames = [kp.co[0] for kp in kps]
            intervals = [frames[i+1] - frames[i] for i in range(len(frames)-1)]
            avg_interval = sum(intervals) / len(intervals)

            if avg_interval < 0.001:
                continue

            # 标记异常帧 (间隔偏差超过阈值的)
            remove_indices = []
            for i, interval in enumerate(intervals):
                deviation = abs(interval - avg_interval) / avg_interval
                if deviation > self.threshold and interval < avg_interval:
                    # 间隔过密的帧标记删除 (保留第一帧)
                    remove_indices.append(i + 1)

            # 从后往前删除
            for idx in reversed(remove_indices):
                if 0 < idx < len(kps) - 1:  # 不删首尾帧
                    kps.remove(kps[idx])
                    total_removed += 1

        self.report({'INFO'}, f'帧缩放修正完成: 清除 {total_removed} 个异常关键帧')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 关键帧精简 (Keyframe Reduce)
# ──────────────────────────────────────────────

class DH_OT_KeyframeReduce(bpy.types.Operator):
    """在误差范围内删除冗余关键帧，减少数据量"""
    bl_idname = 'donghua.keyframe_reduce'
    bl_label = '关键帧精简'
    bl_description = '删除值变化很小的中间关键帧，保持动画曲线形状不变'
    bl_options = {'UNDO'}

    tolerance: bpy.props.FloatProperty(
        name='容差',
        description='值变化小于此阈值的中间关键帧将被删除',
        default=0.001, min=0.0001, max=0.1,
        precision=4,
    )
    selected_only: bpy.props.BoolProperty(
        name='仅选中骨骼',
        default=True,
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'tolerance')
        layout.prop(self, 'selected_only')

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        if self.selected_only:
            bone_names = {pb.name for pb in get_selected_pose_bones(context)}
            if not bone_names:
                self.report({'WARNING'}, '没有选中任何骨骼')
                return {'CANCELLED'}
        else:
            bone_names = None

        total_removed = 0

        for fc in action.fcurves:
            if 'pose.bones[' not in fc.data_path:
                continue
            try:
                bname = fc.data_path.split('"')[1]
            except IndexError:
                continue
            if bone_names is not None and bname not in bone_names:
                continue

            kps = fc.keyframe_points
            if len(kps) < 3:
                continue

            # 从后向前扫描，标记可删除的中间帧
            remove_indices = []
            i = 1
            while i < len(kps) - 1:
                prev_val = kps[i - 1].co[1]
                curr_val = kps[i].co[1]
                next_val = kps[i + 1].co[1]

                # 中间帧的值与前后的线性插值只差很小，可删除
                t = (kps[i].co[0] - kps[i-1].co[0])
                total_t = (kps[i+1].co[0] - kps[i-1].co[0])
                if total_t > 0:
                    ratio = t / total_t
                    interpolated = prev_val + (next_val - prev_val) * ratio
                    if abs(curr_val - interpolated) < self.tolerance:
                        remove_indices.append(i)
                i += 1

            for idx in reversed(remove_indices):
                kps.remove(kps[idx])
                total_removed += 1

        self.report({'INFO'}, f'关键帧精简完成: 删除 {total_removed} 个冗余关键帧')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 重复关键帧清理
# ──────────────────────────────────────────────

class DH_OT_CleanDuplicateKeys(bpy.types.Operator):
    """清除连续值相同的关键帧（仅保留首尾）"""
    bl_idname = 'donghua.clean_duplicate_keys'
    bl_label = '清除重复帧'
    bl_description = '删除连续值完全相同的中间关键帧，仅保留变化点'
    bl_options = {'UNDO'}

    selected_only: bpy.props.BoolProperty(
        name='仅选中骨骼',
        default=False,
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        if self.selected_only:
            bone_names = {pb.name for pb in get_selected_pose_bones(context)}
        else:
            bone_names = None

        total_removed = 0

        for fc in action.fcurves:
            if 'pose.bones[' not in fc.data_path:
                continue
            try:
                bname = fc.data_path.split('"')[1]
            except IndexError:
                continue
            if bone_names is not None and bname not in bone_names:
                continue

            kps = fc.keyframe_points
            if len(kps) < 3:
                continue

            # 查找连续相同值的段落
            remove_indices = []
            i = 1
            while i < len(kps) - 1:
                if (abs(kps[i].co[1] - kps[i-1].co[1]) < 1e-6 and
                        abs(kps[i].co[1] - kps[i+1].co[1]) < 1e-6):
                    remove_indices.append(i)
                i += 1

            for idx in reversed(remove_indices):
                kps.remove(kps[idx])
                total_removed += 1

        self.report({'INFO'}, f'重复帧清理完成: 删除 {total_removed} 个重复关键帧')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# F-Curve 诊断
# ──────────────────────────────────────────────

class DH_OT_DiagnoseFCurves(bpy.types.Operator):
    """诊断 F-Curve 状态: 空曲线、孤立曲线、关键帧统计"""
    bl_idname = 'donghua.diagnose_fcurves'
    bl_label = 'F-Curve 诊断'
    bl_description = '扫描所有动画曲线，报告空曲线、无效引用和关键帧统计'
    bl_options = set()

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        total = 0
        empty = 0
        orphan = 0
        bone_stats = {}
        total_keys = 0

        for fc in action.fcurves:
            total += 1
            n_keys = len(fc.keyframe_points)
            total_keys += n_keys

            if n_keys == 0:
                empty += 1
                continue

            if 'pose.bones[' in fc.data_path:
                try:
                    bname = fc.data_path.split('"')[1]
                except IndexError:
                    bname = '???'

                if arm.data.bones.get(bname) is None:
                    orphan += 1

                if bname not in bone_stats:
                    bone_stats[bname] = 0
                bone_stats[bname] += n_keys

        # 报告
        lines = [
            f'F-Curve 诊断完成:',
            f'  总曲线: {total}',
            f'  总关键帧: {total_keys}',
            f'  空曲线: {empty}',
            f'  孤立曲线(骨骼已删除): {orphan}',
            f'  活跃骨骼数: {len(bone_stats)}',
        ]

        if bone_stats:
            top = sorted(bone_stats.items(), key=lambda x: -x[1])[:5]
            lines.append('  关键帧最多的5个骨骼:')
            for name, count in top:
                lines.append(f'    {name}: {count}')

        for line in lines:
            self.report({'INFO'}, line)

        return {'FINISHED'}


# ──────────────────────────────────────────────
# 清理孤立 F-Curve
# ──────────────────────────────────────────────

class DH_OT_CleanOrphanFCurves(bpy.types.Operator):
    """删除引用已不存在骨骼的 F-Curve 和空 F-Curve"""
    bl_idname = 'donghua.clean_orphan_fcurves'
    bl_label = '清理孤立曲线'
    bl_description = '删除空的或引用了不存在骨骼的 F-Curve'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action
        removed = 0

        for fc in list(action.fcurves):
            # 空 F-Curve
            if len(fc.keyframe_points) == 0:
                action.fcurves.remove(fc)
                removed += 1
                continue

            # 孤立骨骼引用
            if 'pose.bones[' in fc.data_path:
                try:
                    bname = fc.data_path.split('"')[1]
                except IndexError:
                    continue
                if arm.data.bones.get(bname) is None:
                    action.fcurves.remove(fc)
                    removed += 1

        self.report({'INFO'}, f'已清理 {removed} 条孤立/空 F-Curve')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 动画序列间隔工具
# ──────────────────────────────────────────────

class DH_OT_ShiftAnimGroups(bpy.types.Operator):
    """在动画组之间插入间隔帧，避免序列首尾关键帧冲突"""
    bl_idname = 'donghua.shift_anim_groups'
    bl_label = '添加序列间隔'
    bl_description = '在M3动画组之间自动插入间隔帧（参考SC2标准最少10帧间隔）'
    bl_options = {'UNDO'}

    gap_frames: bpy.props.IntProperty(
        name='间隔帧数',
        description='每个动画组之间的间隔帧数',
        default=10, min=1, max=100,
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and len(arm.m3_animation_groups) > 1

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'gap_frames')
        layout.label(text='SC2 标准推荐: ≥10 帧间隔', icon='INFO')

    def execute(self, context):
        arm = get_arm_obj(context)
        groups = arm.m3_animation_groups

        # 按起始帧排序获取索引
        sorted_indices = sorted(range(len(groups)), key=lambda i: groups[i].frame_start)

        # 检查当前间隔
        adjustments = 0
        for i in range(1, len(sorted_indices)):
            prev = groups[sorted_indices[i - 1]]
            curr = groups[sorted_indices[i]]

            current_gap = curr.frame_start - prev.frame_end
            if current_gap < self.gap_frames:
                needed = self.gap_frames - current_gap
                # 后移当前及之后的所有组
                for j in range(i, len(sorted_indices)):
                    g = groups[sorted_indices[j]]
                    g.frame_start += needed
                    g.frame_end += needed
                adjustments += 1

        if adjustments > 0:
            self.report({'INFO'}, f'已调整 {adjustments} 个动画组的间隔 (至少 {self.gap_frames} 帧)')
        else:
            self.report({'INFO'}, f'所有动画组间隔已满足要求 (≥{self.gap_frames} 帧)')

        return {'FINISHED'}


def register_props():
    pass


classes = (
    DH_OT_FrameScaleCorrection,
    DH_OT_KeyframeReduce,
    DH_OT_CleanDuplicateKeys,
    DH_OT_DiagnoseFCurves,
    DH_OT_CleanOrphanFCurves,
    DH_OT_ShiftAnimGroups,
)
