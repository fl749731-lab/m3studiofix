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
核心动画工具：
- 批量关键帧操作
- 动画拷贝/镜像
- 快速 Pose 操作
"""

import bpy
import mathutils
from math import radians


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def get_arm_obj(context):
    """获取当前骨架对象"""
    ob = context.object
    if not ob:
        return None
    if ob.type == 'ARMATURE':
        return ob
    if ob.type == 'MESH' and ob.parent and ob.parent.type == 'ARMATURE':
        return ob.parent
    return None


def get_selected_pose_bones(context):
    """获取选中的姿态骨骼"""
    arm = get_arm_obj(context)
    if not arm or arm.mode != 'POSE':
        return []
    return [pb for pb in arm.pose.bones if pb.bone.select]


def get_mirror_name(name):
    """自动推算镜像骨骼名称。支持 _L/_R, .L/.R, Left/Right 后缀"""
    mirrors = [
        ('_L', '_R'), ('_R', '_L'),
        ('.L', '.R'), ('.R', '.L'),
        ('_l', '_r'), ('_r', '_l'),
        ('.l', '.r'), ('.r', '.l'),
        ('Left', 'Right'), ('Right', 'Left'),
        ('left', 'right'), ('right', 'left'),
    ]
    for src, dst in mirrors:
        if name.endswith(src):
            return name[:-len(src)] + dst
    return None


# ──────────────────────────────────────────────
# 批量关键帧操作
# ──────────────────────────────────────────────

class DH_OT_KeyAll(bpy.types.Operator):
    """为选中骨骼批量插入 LocRotScale 关键帧"""
    bl_idname = 'donghua.key_all'
    bl_label = '全部打帧'
    bl_description = '为所有选中骨骼插入 位置/旋转/缩放 关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        for pb in bones:
            pb.keyframe_insert(data_path='location', group=pb.name)
            pb.keyframe_insert(data_path='rotation_quaternion', group=pb.name)
            pb.keyframe_insert(data_path='scale', group=pb.name)
        self.report({'INFO'}, f'已为 {len(bones)} 个骨骼插入关键帧')
        return {'FINISHED'}


class DH_OT_KeyLoc(bpy.types.Operator):
    """为选中骨骼插入位置关键帧"""
    bl_idname = 'donghua.key_loc'
    bl_label = '位置打帧'
    bl_description = '为选中骨骼插入位置关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        for pb in bones:
            pb.keyframe_insert(data_path='location', group=pb.name)
        self.report({'INFO'}, f'已为 {len(bones)} 个骨骼插入位置关键帧')
        return {'FINISHED'}


class DH_OT_KeyRot(bpy.types.Operator):
    """为选中骨骼插入旋转关键帧"""
    bl_idname = 'donghua.key_rot'
    bl_label = '旋转打帧'
    bl_description = '为选中骨骼插入旋转关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        for pb in bones:
            pb.keyframe_insert(data_path='rotation_quaternion', group=pb.name)
        self.report({'INFO'}, f'已为 {len(bones)} 个骨骼插入旋转关键帧')
        return {'FINISHED'}


class DH_OT_KeyScale(bpy.types.Operator):
    """为选中骨骼插入缩放关键帧"""
    bl_idname = 'donghua.key_scale'
    bl_label = '缩放打帧'
    bl_description = '为选中骨骼插入缩放关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        for pb in bones:
            pb.keyframe_insert(data_path='scale', group=pb.name)
        self.report({'INFO'}, f'已为 {len(bones)} 个骨骼插入缩放关键帧')
        return {'FINISHED'}


class DH_OT_DeleteKeys(bpy.types.Operator):
    """删除选中骨骼在当前帧的所有关键帧"""
    bl_idname = 'donghua.delete_keys'
    bl_label = '删除当前帧'
    bl_description = '删除选中骨骼在当前帧的所有关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        count = 0
        for pb in bones:
            for path in ['location', 'rotation_quaternion', 'scale']:
                try:
                    pb.keyframe_delete(data_path=path)
                    count += 1
                except RuntimeError:
                    pass
        self.report({'INFO'}, f'已删除 {count} 条关键帧')
        return {'FINISHED'}


class DH_OT_ClearAllKeys(bpy.types.Operator):
    """清除选中骨骼的全部关键帧"""
    bl_idname = 'donghua.clear_all_keys'
    bl_label = '清除全部关键帧'
    bl_description = '清除选中骨骼在所有帧上的关键帧数据'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and context.mode == 'POSE' and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        arm = get_arm_obj(context)
        action = arm.animation_data.action
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        bone_names = {pb.name for pb in bones}
        removed = 0
        for fc in list(action.fcurves):
            # fcurve data_path 形如 pose.bones["BoneName"].location 等
            for bn in bone_names:
                if f'pose.bones["{bn}"]' in fc.data_path:
                    action.fcurves.remove(fc)
                    removed += 1
                    break
        self.report({'INFO'}, f'已清除 {removed} 条 F-Curve')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# Pose 操作
# ──────────────────────────────────────────────

class DH_OT_ResetPose(bpy.types.Operator):
    """将选中骨骼重置为静止姿态"""
    bl_idname = 'donghua.reset_pose'
    bl_label = '重置姿态'
    bl_description = '将选中骨骼的位置/旋转/缩放重置为静止状态'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        for pb in bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        self.report({'INFO'}, f'已重置 {len(bones)} 个骨骼')
        return {'FINISHED'}


class DH_OT_CopyPose(bpy.types.Operator):
    """复制选中骨骼的当前姿态"""
    bl_idname = 'donghua.copy_pose'
    bl_label = '复制姿态'
    bl_description = '将选中骨骼的变换数据复制到剪贴板'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        scene = context.scene
        scene.dh_pose_clipboard.clear()
        for pb in bones:
            entry = scene.dh_pose_clipboard.add()
            entry.name = pb.name
            entry.location = pb.location.copy()
            entry.rotation = pb.rotation_quaternion.copy()
            entry.scale = pb.scale.copy()
        self.report({'INFO'}, f'已复制 {len(bones)} 个骨骼姿态')
        return {'FINISHED'}


class DH_OT_PastePose(bpy.types.Operator):
    """粘贴先前复制的姿态"""
    bl_idname = 'donghua.paste_pose'
    bl_label = '粘贴姿态'
    bl_description = '将剪贴板中的姿态粘贴到同名骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (get_arm_obj(context) is not None and context.mode == 'POSE'
                and len(context.scene.dh_pose_clipboard) > 0)

    def execute(self, context):
        arm = get_arm_obj(context)
        clipboard = context.scene.dh_pose_clipboard
        count = 0
        for entry in clipboard:
            pb = arm.pose.bones.get(entry.name)
            if pb:
                pb.location = entry.location
                pb.rotation_quaternion = entry.rotation
                pb.scale = entry.scale
                count += 1
        self.report({'INFO'}, f'已粘贴 {count} 个骨骼姿态')
        return {'FINISHED'}


class DH_OT_PastePoseMirrored(bpy.types.Operator):
    """镜像粘贴姿态（X 轴）"""
    bl_idname = 'donghua.paste_pose_mirrored'
    bl_label = '镜像粘贴'
    bl_description = '将剪贴板中的姿态以 X 轴镜像粘贴到对称骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (get_arm_obj(context) is not None and context.mode == 'POSE'
                and len(context.scene.dh_pose_clipboard) > 0)

    def execute(self, context):
        arm = get_arm_obj(context)
        clipboard = context.scene.dh_pose_clipboard
        count = 0
        for entry in clipboard:
            mirror_name = get_mirror_name(entry.name)
            target_name = mirror_name if mirror_name else entry.name
            pb = arm.pose.bones.get(target_name)
            if pb:
                # 镜像位置: X 翻转
                pb.location = (-entry.location[0], entry.location[1], entry.location[2])
                # 镜像四元数旋转: (W, -X, Y, Z) → 还需翻转 Y/Z 分量
                q = entry.rotation
                pb.rotation_quaternion = (q[0], -q[1], q[2], q[3])
                pb.scale = entry.scale.copy()
                count += 1
        self.report({'INFO'}, f'已镜像粘贴 {count} 个骨骼姿态')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 时间线工具
# ──────────────────────────────────────────────

class DH_OT_SetFrameRange(bpy.types.Operator):
    """快速设置帧范围"""
    bl_idname = 'donghua.set_frame_range'
    bl_label = '设置帧范围'
    bl_description = '根据当前 M3 动画组自动设定时间线帧范围'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and len(arm.m3_animation_groups) > 0

    def execute(self, context):
        arm = get_arm_obj(context)
        idx = arm.m3_animation_groups_index
        if idx < 0 or idx >= len(arm.m3_animation_groups):
            self.report({'WARNING'}, '未选择动画组')
            return {'CANCELLED'}
        grp = arm.m3_animation_groups[idx]
        context.scene.frame_start = grp.frame_start
        context.scene.frame_end = grp.frame_end - 1
        context.scene.frame_current = grp.frame_start
        self.report({'INFO'}, f'帧范围 → {grp.frame_start} - {grp.frame_end - 1} ({grp.name})')
        return {'FINISHED'}


class DH_OT_KeyframeSteppedAll(bpy.types.Operator):
    """为选中骨骼按间隔批量打帧（阶梯动画）"""
    bl_idname = 'donghua.keyframe_stepped'
    bl_label = '阶梯打帧'
    bl_description = '在帧范围内按固定间隔为选中骨骼插入关键帧'
    bl_options = {'UNDO'}

    step: bpy.props.IntProperty(name='间隔帧数', default=5, min=1, max=60)

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        self.layout.prop(self, 'step')

    def execute(self, context):
        bones = get_selected_pose_bones(context)
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        start = context.scene.frame_start
        end = context.scene.frame_end
        count = 0
        for frame in range(start, end + 1, self.step):
            context.scene.frame_set(frame)
            for pb in bones:
                pb.keyframe_insert(data_path='location', group=pb.name)
                pb.keyframe_insert(data_path='rotation_quaternion', group=pb.name)
                pb.keyframe_insert(data_path='scale', group=pb.name)
                count += 1
        self.report({'INFO'}, f'已在 {(end - start) // self.step + 1} 帧上为 {len(bones)} 个骨骼打帧')
        return {'FINISHED'}


class DH_OT_SelectKeyframedBones(bpy.types.Operator):
    """选择在当前帧有关键帧的所有骨骼"""
    bl_idname = 'donghua.select_keyed_bones'
    bl_label = '选择已打帧骨骼'
    bl_description = '自动选中在当前帧拥有关键帧数据的所有骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and context.mode == 'POSE' and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action
        frame = context.scene.frame_current
        keyed_bones = set()

        for fc in action.fcurves:
            if 'pose.bones[' not in fc.data_path:
                continue
            # 提取骨骼名称
            try:
                name = fc.data_path.split('"')[1]
            except IndexError:
                continue
            for kp in fc.keyframe_points:
                if int(kp.co[0]) == frame:
                    keyed_bones.add(name)
                    break

        # 全取消选择
        for pb in arm.pose.bones:
            pb.bone.select = False

        count = 0
        for bn in keyed_bones:
            bone = arm.data.bones.get(bn)
            if bone:
                bone.select = True
                count += 1

        self.report({'INFO'}, f'已选中 {count} 个在第 {frame} 帧有关键帧的骨骼')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 姿态剪贴板属性组
# ──────────────────────────────────────────────

class DH_PoseClipboardEntry(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    location: bpy.props.FloatVectorProperty(size=3)
    rotation: bpy.props.FloatVectorProperty(size=4) # Quaternion WXYZ
    scale: bpy.props.FloatVectorProperty(size=3, default=(1, 1, 1))


def register_props():
    bpy.types.Scene.dh_pose_clipboard = bpy.props.CollectionProperty(type=DH_PoseClipboardEntry)


classes = (
    DH_PoseClipboardEntry,
    DH_OT_KeyAll,
    DH_OT_KeyLoc,
    DH_OT_KeyRot,
    DH_OT_KeyScale,
    DH_OT_DeleteKeys,
    DH_OT_ClearAllKeys,
    DH_OT_ResetPose,
    DH_OT_CopyPose,
    DH_OT_PastePose,
    DH_OT_PastePoseMirrored,
    DH_OT_SetFrameRange,
    DH_OT_KeyframeSteppedAll,
    DH_OT_SelectKeyframedBones,
)
