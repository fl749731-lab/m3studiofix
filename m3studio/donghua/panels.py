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
M3 动画工作站面板（3D 视图侧边栏 N 面板）
"""

import bpy
from .anim_tools import get_arm_obj
from .look_at import get_lookat_constraint, get_lookat_bones


# ──────────────────────────────────────────────
# 主面板
# ──────────────────────────────────────────────

class DH_PT_MainPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_main'
    bl_label = 'M3 动画工作站'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def draw(self, context):
        layout = self.layout
        arm = get_arm_obj(context)

        # 当前动画组信息
        if arm.m3_animation_groups:
            idx = arm.m3_animation_groups_index
            if 0 <= idx < len(arm.m3_animation_groups):
                grp = arm.m3_animation_groups[idx]
                box = layout.box()
                row = box.row()
                row.label(text=f'当前动画组: {grp.name}', icon='ACTION')
                row = box.row(align=True)
                row.label(text=f'帧: {grp.frame_start} - {grp.frame_end - 1}')
                row.label(text=f'频率: {grp.frequency}')
                if grp.not_looping:
                    row.label(text='不循环', icon='DECORATE_UNLOCKED')
                else:
                    row.label(text='循环', icon='FILE_REFRESH')
        else:
            box = layout.box()
            box.label(text='暂无动画组', icon='INFO')


# ──────────────────────────────────────────────
# 关键帧面板
# ──────────────────────────────────────────────

class DH_PT_KeyframePanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_keyframe'
    bl_label = '快速打帧'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def draw(self, context):
        layout = self.layout

        # 选中骨骼计数
        arm = get_arm_obj(context)
        selected = sum(1 for pb in arm.pose.bones if pb.bone.select)
        layout.label(text=f'选中骨骼: {selected}', icon='BONE_DATA')

        # 插帧按钮组
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator('donghua.key_all', text='全部', icon='KEYFRAME')
        row = col.row(align=True)
        row.operator('donghua.key_loc', text='位置', icon='CON_LOCLIKE')
        row.operator('donghua.key_rot', text='旋转', icon='CON_ROTLIKE')
        row.operator('donghua.key_scale', text='缩放', icon='CON_SIZELIKE')

        layout.separator()

        # 删帧按钮
        row = layout.row(align=True)
        row.operator('donghua.delete_keys', text='删除当前帧', icon='KEYFRAME_HLT')
        row.operator('donghua.clear_all_keys', text='清除全部', icon='CANCEL')

        layout.separator()

        # 高级插帧
        col = layout.column(align=True)
        col.operator('donghua.keyframe_stepped', text='阶梯打帧', icon='IPO_CONSTANT')
        col.operator('donghua.batch_key_range', text='首尾打帧', icon='ARROW_LEFTRIGHT')
        col.operator('donghua.select_keyed_bones', text='选择已打帧骨骼', icon='RESTRICT_SELECT_OFF')


# ──────────────────────────────────────────────
# 姿态面板
# ──────────────────────────────────────────────

class DH_PT_PosePanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_pose'
    bl_label = '姿态操作'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator('donghua.reset_pose', text='重置姿态', icon='LOOP_BACK')

        layout.separator()
        layout.label(text='姿态剪贴板:', icon='COPYDOWN')

        clipboard_count = len(context.scene.dh_pose_clipboard)

        col = layout.column(align=True)
        col.operator('donghua.copy_pose', text=f'复制姿态', icon='COPY_ID')

        row = col.row(align=True)
        sub = row.row(align=True)
        sub.enabled = clipboard_count > 0
        sub.operator('donghua.paste_pose', text='粘贴', icon='PASTEDOWN')
        sub.operator('donghua.paste_pose_mirrored', text='镜像粘贴', icon='MOD_MIRROR')

        if clipboard_count > 0:
            layout.label(text=f'剪贴板: {clipboard_count} 个骨骼', icon='INFO')


# ──────────────────────────────────────────────
# 动画模板面板
# ──────────────────────────────────────────────

class DH_PT_TemplatePanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_template'
    bl_label = '动画模板'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def draw(self, context):
        layout = self.layout
        arm = get_arm_obj(context)

        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator('donghua.create_from_template', icon='PRESET', text='从模板创建动画组')
        col.operator('donghua.create_single_group', icon='ADD', text='手动创建动画组')

        # 时间线快捷
        layout.separator()
        layout.label(text='时间线:', icon='TIME')
        row = layout.row()
        row.operator('donghua.set_frame_range', text='同步帧范围', icon='PREVIEW_RANGE')

        # 当前动画组数量
        layout.separator()
        box = layout.box()
        box.label(text=f'动画组数量: {len(arm.m3_animation_groups)}', icon='NLA')
        if arm.m3_animation_groups:
            for i, grp in enumerate(arm.m3_animation_groups):
                row = box.row(align=True)
                icon = 'LAYER_ACTIVE' if i == arm.m3_animation_groups_index else 'LAYER_USED'
                row.label(text=grp.name, icon=icon)
                row.label(text=f'{grp.frame_start}-{grp.frame_end - 1}')


# ──────────────────────────────────────────────
# 骨骼选择集面板
# ──────────────────────────────────────────────

class DH_PT_BoneSetPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_bone_sets'
    bl_label = '骨骼选择集'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def draw(self, context):
        layout = self.layout
        arm = get_arm_obj(context)

        # 选择集列表
        row = layout.row()
        row.template_list(
            'DH_UL_bone_set_list', '',
            arm, 'dh_bone_sets',
            arm, 'dh_bone_sets_index',
            rows=3,
        )
        col = row.column(align=True)
        col.operator('donghua.save_bone_set', icon='ADD', text='')
        col.operator('donghua.remove_bone_set', icon='REMOVE', text='')

        # 操作按钮
        if arm.dh_bone_sets and 0 <= arm.dh_bone_sets_index < len(arm.dh_bone_sets):
            bs = arm.dh_bone_sets[arm.dh_bone_sets_index]

            col = layout.column(align=True)
            col.scale_y = 1.2
            col.operator('donghua.load_bone_set', text=f'选中 "{bs.name}"', icon='RESTRICT_SELECT_OFF')

            row = layout.row(align=True)
            row.operator('donghua.add_to_bone_set', text='追加选中', icon='ADD')
            row.operator('donghua.update_bone_set', text='覆盖更新', icon='FILE_REFRESH')

            # 显示骨骼列表
            box = layout.box()
            box.label(text=f'骨骼 ({len(bs.bones)}):', icon='BONE_DATA')
            col = box.column(align=True)
            for entry in bs.bones:
                row = col.row()
                icon = 'BONE_DATA' if arm.data.bones.get(entry.name) else 'ERROR'
                row.label(text=entry.name, icon=icon)


# ──────────────────────────────────────────────
# 注视追踪面板
# ──────────────────────────────────────────────

class DH_PT_LookAtPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_lookat'
    bl_label = '注视追踪'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        arm = get_arm_obj(context)

        # ── 目标设置 ──
        box = layout.box()
        box.label(text='目标对象:', icon='EMPTY_ARROWS')
        row = box.row(align=True)
        row.prop(scene, 'dh_lookat_target', text='')
        row.operator('donghua.create_lookat_target', text='', icon='ADD')

        # ── 约束参数 ──
        col = layout.column(align=True)
        col.prop(scene, 'dh_lookat_constraint_type', text='类型')
        col.prop(scene, 'dh_lookat_track_axis', text='追踪轴')

        # Track To 模式才显示向上轴
        if scene.dh_lookat_constraint_type == 'TRACK_TO':
            col.prop(scene, 'dh_lookat_up_axis', text='向上轴')

        col.prop(scene, 'dh_lookat_influence', text='影响度', slider=True)

        layout.separator()

        # ── 操作按钮 ──
        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator('donghua.add_lookat', text='添加注视', icon='HIDE_OFF')

        row = col.row(align=True)
        row.operator('donghua.update_lookat_influence', text='同步影响度', icon='FILE_REFRESH')
        row.operator('donghua.remove_lookat', text='移除', icon='X')

        layout.separator()

        # ── 辅助工具 ──
        row = layout.row(align=True)
        row.operator('donghua.auto_detect_head_eye', text='自动查找头/眼', icon='VIEWZOOM')
        row.operator('donghua.select_lookat_bones', text='选择注视骨骼', icon='RESTRICT_SELECT_OFF')

        # ── 当前状态 ──
        lookat_bones = get_lookat_bones(arm)
        if lookat_bones:
            layout.separator()
            box = layout.box()
            box.label(text=f'注视骨骼 ({len(lookat_bones)}):', icon='BONE_DATA')
            col = box.column(align=True)
            for pb in lookat_bones:
                con = get_lookat_constraint(pb)
                row = col.row(align=True)
                row.label(text=pb.name, icon='BONE_DATA')
                row.label(text=f'{con.influence:.0%}' if con else '?')

        # ── 烘焙区 ──
        layout.separator()
        box = layout.box()
        box.label(text='动画导出:', icon='EXPORT')

        if lookat_bones:
            box.label(text=f'⚠ {len(lookat_bones)} 个约束待烘焙', icon='ERROR')
            row = box.row(align=True)
            row.operator('donghua.key_lookat_influence', text='影响度打帧', icon='KEYFRAME')

        row = box.row()
        row.scale_y = 1.5
        row.enabled = len(lookat_bones) > 0
        row.operator('donghua.bake_lookat', text='烘焙注视 → 关键帧', icon='ACTION')

        if not lookat_bones:
            box.label(text='✓ 无待烘焙约束', icon='CHECKMARK')

        # ── M3 Turret 快速配置（游戏内实时注视）──
        layout.separator()
        box = layout.box()
        box.label(text='游戏内实时注视 (Turret):', icon='CON_TRACKTO')

        turret_count = len(arm.m3_turrets) if hasattr(arm, 'm3_turrets') else 0
        part_count = sum(len(t.parts) for t in arm.m3_turrets) if turret_count else 0
        if part_count > 0:
            box.label(text=f'已有 {turret_count} 个 Turret / {part_count} 个 Part', icon='CHECKMARK')

        col = box.column(align=True)
        col.label(text='预设一键配置:', icon='PRESET')
        row = col.row(align=True)
        op = row.operator('donghua.quick_turret_setup', text='武器', icon='TRACKING_FORWARDS')
        op.preset = 'WEAPON'
        op = row.operator('donghua.quick_turret_setup', text='注视', icon='HIDE_OFF')
        op.preset = 'LOOKAT'

        row = col.row(align=True)
        op = row.operator('donghua.quick_turret_setup', text='仅 Yaw', icon='LOOP_FORWARDS')
        op.preset = 'YAW_ONLY'
        op = row.operator('donghua.quick_turret_setup', text='仅 Pitch', icon='SORT_DESC')
        op.preset = 'PITCH_ONLY'

        col.separator()
        col.operator('donghua.turret_from_selection', text='多段联动 (底座+炮管)', icon='LINK_BLEND')


# ──────────────────────────────────────────────
# 动画修正面板
# ──────────────────────────────────────────────

class DH_PT_AnimFixPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_animfix'
    bl_label = '动画修正'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and arm.animation_data and arm.animation_data.action

    def draw(self, context):
        layout = self.layout
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        # 统计信息
        n_fcurves = len(action.fcurves)
        n_keys = sum(len(fc.keyframe_points) for fc in action.fcurves)
        box = layout.box()
        row = box.row()
        row.label(text=f'F-Curves: {n_fcurves}', icon='GRAPH')
        row.label(text=f'关键帧: {n_keys}')

        # ── 清理工具 ──
        col = layout.column(align=True)
        col.label(text='关键帧清理:', icon='BRUSH_DATA')
        col.operator('donghua.keyframe_reduce', text='关键帧精简', icon='KEYFRAME')
        col.operator('donghua.clean_duplicate_keys', text='清除重复帧', icon='CANCEL')
        col.operator('donghua.frame_scale_correction', text='帧缩放修正', icon='MOD_TIME')

        layout.separator()

        # ── 诊断工具 ──
        col = layout.column(align=True)
        col.label(text='诊断 & 清理:', icon='VIEWZOOM')
        col.operator('donghua.diagnose_fcurves', text='F-Curve 诊断', icon='INFO')
        col.operator('donghua.clean_orphan_fcurves', text='清理孤立曲线', icon='TRASH')

        layout.separator()

        # ── 序列管理 ──
        if len(arm.m3_animation_groups) > 1:
            col = layout.column(align=True)
            col.label(text='序列间隔:', icon='NLA_PUSHDOWN')
            col.operator('donghua.shift_anim_groups', text='添加序列间隔', icon='TRACKING_FORWARDS')


# ──────────────────────────────────────────────
# SC2 场景工具面板
# ──────────────────────────────────────────────

class DH_PT_SC2ScenePanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_donghua_sc2scene'
    bl_label = 'SC2 场景工具'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3 动画'
    bl_parent_id = 'VIEW3D_PT_donghua_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def draw(self, context):
        layout = self.layout
        arm = get_arm_obj(context)

        # ── 挂点工具 ──
        box = layout.box()
        box.label(text='挂点管理:', icon='EMPTY_ARROWS')
        col = box.column(align=True)
        col.operator('donghua.create_base_attach_points', text='创建标准挂点', icon='ADD')

        if context.mode == 'POSE':
            col.operator('donghua.create_custom_attach_point', text='在骨骼处创建挂点', icon='BONE_DATA')

        # 显示现有挂点数量
        attach_count = sum(1 for o in bpy.data.objects
                         if o.type == 'EMPTY' and o.name.startswith('Ref_'))
        if attach_count > 0:
            box.label(text=f'现有挂点: {attach_count}', icon='CHECKMARK')

        layout.separator()

        # ── 事件工具 ──
        box = layout.box()
        box.label(text='事件骨骼:', icon='OUTLINER_OB_EMPTY')
        col = box.column(align=True)
        col.operator('donghua.create_event_bone', text='创建事件骨骼', icon='ADD')

        if context.mode in {'POSE', 'EDIT_ARMATURE'}:
            col.operator('donghua.rename_event_bones', text='批量重命名事件', icon='SORTALPHA')

        if arm.animation_data and arm.animation_data.action:
            col.operator('donghua.combine_duplicate_events', text='合并重复事件', icon='AUTOMERGE_ON')

        # 显示现有事件骨骼数量
        event_count = sum(1 for b in arm.data.bones if b.name.startswith('Evt_'))
        if event_count > 0:
            box.label(text=f'事件骨骼: {event_count}', icon='CHECKMARK')

        layout.separator()

        # ── 显示控制 ──
        box = layout.box()
        opts = arm.m3_options
        box.label(text='辅助显示:', icon='HIDE_OFF')
        col = box.column(align=True)

        # 挂点: 显示当前状态图标
        icon_att = 'HIDE_OFF' if opts.draw_attach_points else 'HIDE_ON'
        op = col.operator('donghua.toggle_helper_vis', text='挂点', icon=icon_att, depress=opts.draw_attach_points)
        op.helper_type = 'ATTACH'

        # 碰撞体
        icon_hit = 'HIDE_OFF' if opts.draw_hittests else 'HIDE_ON'
        op = col.operator('donghua.toggle_helper_vis', text='碰撞体', icon=icon_hit, depress=opts.draw_hittests)
        op.helper_type = 'HITTEST'

        # 粒子/力场
        icon_par = 'HIDE_OFF' if opts.draw_particles else 'HIDE_ON'
        op = col.operator('donghua.toggle_helper_vis', text='粒子/力场', icon=icon_par, depress=opts.draw_particles)
        op.helper_type = 'PARTICLES'

        # 全部
        col.separator()
        op = col.operator('donghua.toggle_helper_vis', text='全部 显示/隐藏', icon='GHOST_DISABLED')
        op.helper_type = 'ALL'


def register_props():
    pass


classes = (
    DH_PT_MainPanel,
    DH_PT_KeyframePanel,
    DH_PT_PosePanel,
    DH_PT_TemplatePanel,
    DH_PT_BoneSetPanel,
    DH_PT_LookAtPanel,
    DH_PT_AnimFixPanel,
    DH_PT_SC2ScenePanel,
)

