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
SC2 M3 动画模板：
- 一键创建常见动画组（Stand、Walk、Attack、Death、Spell 等）
- 自动设置帧范围、频率、循环等参数
- 批量创建标准动画组集合
"""

import bpy
from .anim_tools import get_arm_obj

# ──────────────────────────────────────────────
# SC2 常用动画模板定义
# ──────────────────────────────────────────────
# 格式: (名称, 帧开始, 帧结束, 频率, 循环, 移动速度)

SC2_ANIM_TEMPLATES = {
    'UNIT_BASIC': {
        'label': '单位基础',
        'description': '基本站立/行走/攻击/死亡',
        'groups': [
            ('Stand',   0,   60,  100, False, 0.0),
            ('Walk',    70,  130, 100, False, 2.25),
            ('Attack',  140, 180, 100, True,  0.0),
            ('Death',   190, 250, 100, True,  0.0),
        ],
    },
    'UNIT_FULL': {
        'label': '单位完整',
        'description': '完整单位动画集（含待机变体、施法等）',
        'groups': [
            ('Stand',       0,    60,  100, False, 0.0),
            ('Stand Work',  70,   130, 100, False, 0.0),
            ('Stand Ready', 140,  200, 100, False, 0.0),
            ('Walk',        210,  270, 100, False, 2.25),
            ('Attack',      280,  320, 100, True,  0.0),
            ('Spell',       330,  380, 100, True,  0.0),
            ('Death',       390,  450, 100, True,  0.0),
            ('Birth',       460,  500, 100, True,  0.0),
        ],
    },
    'BUILDING': {
        'label': '建筑',
        'description': '建筑常用动画（待机/建造/工作/死亡）',
        'groups': [
            ('Stand',        0,   80,  100, False, 0.0),
            ('Stand Work',   90,  170, 100, False, 0.0),
            ('Birth',        180, 260, 100, True,  0.0),
            ('Death',        270, 380, 100, True,  0.0),
        ],
    },
    'SPELL_EFFECT': {
        'label': '技能特效',
        'description': '技能特效动画（出生/循环/消亡）',
        'groups': [
            ('Birth',   0,   20, 100, True,  0.0),
            ('Stand',   30,  60, 100, False, 0.0),
            ('Death',   70,  100, 100, True, 0.0),
        ],
    },
    'DOODAD': {
        'label': '装饰物',
        'description': '地图装饰物动画',
        'groups': [
            ('Stand',     0,   120, 100, False, 0.0),
            ('Stand 01',  130, 250, 50,  False, 0.0),
        ],
    },
}


def sc2_template_items(self, context):
    items = []
    for key, tpl in SC2_ANIM_TEMPLATES.items():
        items.append((key, tpl['label'], tpl['description']))
    return items


# ──────────────────────────────────────────────
# 操作符
# ──────────────────────────────────────────────

class DH_OT_CreateFromTemplate(bpy.types.Operator):
    """根据模板一键创建 M3 动画组"""
    bl_idname = 'donghua.create_from_template'
    bl_label = '从模板创建'
    bl_description = '根据 SC2 预设模板批量创建 M3 动画组及其子序列'
    bl_options = {'UNDO'}

    template: bpy.props.EnumProperty(
        name='模板',
        items=sc2_template_items,
    )

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'template', text='模板')
        tpl = SC2_ANIM_TEMPLATES.get(self.template)
        if tpl:
            box = layout.box()
            box.label(text=f'将创建 {len(tpl["groups"])} 个动画组:', icon='INFO')
            for name, start, end, freq, no_loop, speed in tpl['groups']:
                row = box.row()
                row.label(text=f'  {name}')
                row.label(text=f'{start}-{end}')
                if no_loop:
                    row.label(text='不循环')
                else:
                    row.label(text='循环')

    def execute(self, context):
        from .. import shared

        arm = get_arm_obj(context)
        tpl = SC2_ANIM_TEMPLATES.get(self.template)
        if not tpl:
            self.report({'ERROR'}, '模板不存在')
            return {'CANCELLED'}

        created = 0
        for name, start, end, freq, no_loop, speed in tpl['groups']:
            # 检查是否已存在同名动画组
            exists = any(g.name == name for g in arm.m3_animation_groups)
            if exists:
                continue

            grp = shared.m3_item_add(arm.m3_animation_groups, name)
            grp.frame_start = start
            grp.frame_end = end
            grp.frequency = freq
            grp.not_looping = no_loop
            grp.movement_speed = speed

            # 自动创建一个子序列并绑定 Action
            anim = shared.m3_item_add(grp.animations, 'full')
            action = bpy.data.actions.new(name=f'{arm.name}_{name}_full')
            anim.action = action

            created += 1

        arm.m3_animation_groups_index = len(arm.m3_animation_groups) - 1
        self.report({'INFO'}, f'已从模板 "{tpl["label"]}" 创建 {created} 个动画组')
        return {'FINISHED'}


class DH_OT_CreateSingleGroup(bpy.types.Operator):
    """快速创建单个 M3 动画组"""
    bl_idname = 'donghua.create_single_group'
    bl_label = '快速创建动画组'
    bl_description = '手动指定参数快速创建一个 M3 动画组'
    bl_options = {'UNDO'}

    group_name: bpy.props.StringProperty(name='名称', default='NewAnim')
    frame_start: bpy.props.IntProperty(name='起始帧', default=0, min=0)
    frame_end: bpy.props.IntProperty(name='结束帧', default=60, min=1)
    frequency: bpy.props.IntProperty(name='频率', default=100, min=0, max=100)
    not_looping: bpy.props.BoolProperty(name='不循环', default=False)
    movement_speed: bpy.props.FloatProperty(name='移动速度', default=0.0, min=0.0)
    create_action: bpy.props.BoolProperty(name='自动创建 Action', default=True)

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'group_name')
        row = layout.row(align=True)
        row.prop(self, 'frame_start')
        row.prop(self, 'frame_end')
        layout.prop(self, 'frequency')
        layout.prop(self, 'not_looping')
        layout.prop(self, 'movement_speed')
        layout.separator()
        layout.prop(self, 'create_action')

    def execute(self, context):
        from .. import shared

        arm = get_arm_obj(context)

        if any(g.name == self.group_name for g in arm.m3_animation_groups):
            self.report({'WARNING'}, f'动画组 "{self.group_name}" 已存在')
            return {'CANCELLED'}

        grp = shared.m3_item_add(arm.m3_animation_groups, self.group_name)
        grp.frame_start = self.frame_start
        grp.frame_end = self.frame_end
        grp.frequency = self.frequency
        grp.not_looping = self.not_looping
        grp.movement_speed = self.movement_speed

        if self.create_action:
            anim = shared.m3_item_add(grp.animations, 'full')
            action = bpy.data.actions.new(name=f'{arm.name}_{self.group_name}_full')
            anim.action = action

        arm.m3_animation_groups_index = len(arm.m3_animation_groups) - 1
        self.report({'INFO'}, f'已创建动画组 "{self.group_name}"')
        return {'FINISHED'}


class DH_OT_BatchKeySelected(bpy.types.Operator):
    """为选中骨骼在当前动画组的首尾帧各打一次关键帧"""
    bl_idname = 'donghua.batch_key_range'
    bl_label = '首尾打帧'
    bl_description = '在当前动画组的起始帧和结束帧为选中骨骼插入关键帧'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return (arm is not None and context.mode == 'POSE'
                and len(arm.m3_animation_groups) > 0)

    def execute(self, context):
        arm = get_arm_obj(context)
        idx = arm.m3_animation_groups_index
        if idx < 0 or idx >= len(arm.m3_animation_groups):
            self.report({'WARNING'}, '未选择动画组')
            return {'CANCELLED'}
        grp = arm.m3_animation_groups[idx]
        bones = [pb for pb in arm.pose.bones if pb.bone.select]
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}

        for frame in [grp.frame_start, grp.frame_end - 1]:
            context.scene.frame_set(frame)
            for pb in bones:
                pb.keyframe_insert(data_path='location', group=pb.name)
                pb.keyframe_insert(data_path='rotation_quaternion', group=pb.name)
                pb.keyframe_insert(data_path='scale', group=pb.name)

        self.report({'INFO'}, f'已在帧 {grp.frame_start} 和 {grp.frame_end - 1} 为 {len(bones)} 个骨骼打帧')
        return {'FINISHED'}


def register_props():
    pass


classes = (
    DH_OT_CreateFromTemplate,
    DH_OT_CreateSingleGroup,
    DH_OT_BatchKeySelected,
)
