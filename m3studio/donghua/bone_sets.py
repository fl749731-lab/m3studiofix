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
骨骼选择集管理：
- 保存当前选中的骨骼为命名集
- 快速加载选择集
- 增量选择 / 排除选择
"""

import bpy
from .anim_tools import get_arm_obj


# ──────────────────────────────────────────────
# 属性组
# ──────────────────────────────────────────────

class DH_BoneSetBone(bpy.types.PropertyGroup):
    """选择集中的一根骨骼"""
    name: bpy.props.StringProperty()


class DH_BoneSet(bpy.types.PropertyGroup):
    """一个骨骼选择集"""
    name: bpy.props.StringProperty(default='新选择集')
    bones: bpy.props.CollectionProperty(type=DH_BoneSetBone)
    color: bpy.props.FloatVectorProperty(
        name='颜色',
        subtype='COLOR',
        size=3,
        min=0.0, max=1.0,
        default=(0.4, 0.7, 1.0),
    )


# ──────────────────────────────────────────────
# 操作符
# ──────────────────────────────────────────────

class DH_OT_SaveBoneSet(bpy.types.Operator):
    """将当前选中的骨骼保存为选择集"""
    bl_idname = 'donghua.save_bone_set'
    bl_label = '保存选择集'
    bl_description = '将当前选中的姿态骨骼保存为一个命名选择集'
    bl_options = {'UNDO'}

    set_name: bpy.props.StringProperty(name='名称', default='选择集')

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        self.layout.prop(self, 'set_name')

    def execute(self, context):
        arm = get_arm_obj(context)
        selected = [pb.name for pb in arm.pose.bones if pb.bone.select]
        if not selected:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}

        bone_sets = arm.dh_bone_sets
        bs = bone_sets.add()
        bs.name = self.set_name
        for bn in selected:
            entry = bs.bones.add()
            entry.name = bn

        arm.dh_bone_sets_index = len(bone_sets) - 1
        self.report({'INFO'}, f'已保存选择集 "{self.set_name}"，含 {len(selected)} 个骨骼')
        return {'FINISHED'}


class DH_OT_LoadBoneSet(bpy.types.Operator):
    """加载选择集并选中对应骨骼"""
    bl_idname = 'donghua.load_bone_set'
    bl_label = '加载选择集'
    bl_description = '选中该选择集中记录的所有骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return (arm is not None and context.mode == 'POSE'
                and arm.dh_bone_sets_index >= 0
                and arm.dh_bone_sets_index < len(arm.dh_bone_sets))

    def execute(self, context):
        arm = get_arm_obj(context)
        bs = arm.dh_bone_sets[arm.dh_bone_sets_index]

        # 先全取消选中
        for pb in arm.pose.bones:
            pb.bone.select = False

        count = 0
        for entry in bs.bones:
            bone = arm.data.bones.get(entry.name)
            if bone:
                bone.select = True
                count += 1

        self.report({'INFO'}, f'已选中 {count} 个骨骼 ({bs.name})')
        return {'FINISHED'}


class DH_OT_AddToBoneSet(bpy.types.Operator):
    """将当前选中骨骼添加到活动选择集"""
    bl_idname = 'donghua.add_to_bone_set'
    bl_label = '添加到选择集'
    bl_description = '将当前选中的骨骼追加到活动选择集'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return (arm is not None and context.mode == 'POSE'
                and arm.dh_bone_sets_index >= 0
                and arm.dh_bone_sets_index < len(arm.dh_bone_sets))

    def execute(self, context):
        arm = get_arm_obj(context)
        bs = arm.dh_bone_sets[arm.dh_bone_sets_index]
        existing = {entry.name for entry in bs.bones}
        selected = [pb.name for pb in arm.pose.bones if pb.bone.select]
        added = 0
        for bn in selected:
            if bn not in existing:
                entry = bs.bones.add()
                entry.name = bn
                added += 1
        self.report({'INFO'}, f'已添加 {added} 个骨骼到 "{bs.name}"')
        return {'FINISHED'}


class DH_OT_RemoveBoneSet(bpy.types.Operator):
    """删除活动选择集"""
    bl_idname = 'donghua.remove_bone_set'
    bl_label = '删除选择集'
    bl_description = '删除当前活动的骨骼选择集'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return (arm is not None
                and arm.dh_bone_sets_index >= 0
                and arm.dh_bone_sets_index < len(arm.dh_bone_sets))

    def execute(self, context):
        arm = get_arm_obj(context)
        idx = arm.dh_bone_sets_index
        name = arm.dh_bone_sets[idx].name
        arm.dh_bone_sets.remove(idx)
        arm.dh_bone_sets_index = max(0, idx - 1)
        self.report({'INFO'}, f'已删除选择集 "{name}"')
        return {'FINISHED'}


class DH_OT_UpdateBoneSet(bpy.types.Operator):
    """用当前选择覆盖活动选择集"""
    bl_idname = 'donghua.update_bone_set'
    bl_label = '更新选择集'
    bl_description = '用当前选中的骨骼覆盖活动选择集'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return (arm is not None and context.mode == 'POSE'
                and arm.dh_bone_sets_index >= 0
                and arm.dh_bone_sets_index < len(arm.dh_bone_sets))

    def execute(self, context):
        arm = get_arm_obj(context)
        bs = arm.dh_bone_sets[arm.dh_bone_sets_index]
        selected = [pb.name for pb in arm.pose.bones if pb.bone.select]
        if not selected:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}
        bs.bones.clear()
        for bn in selected:
            entry = bs.bones.add()
            entry.name = bn
        self.report({'INFO'}, f'已更新选择集 "{bs.name}"，含 {len(selected)} 个骨骼')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# UI 列表
# ──────────────────────────────────────────────

class DH_UL_BoneSetList(bpy.types.UIList):
    bl_idname = 'DH_UL_bone_set_list'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index, flt_flag):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False, icon='GROUP_BONE')
            row.label(text=f'({len(item.bones)})')


def register_props():
    bpy.types.Object.dh_bone_sets = bpy.props.CollectionProperty(type=DH_BoneSet)
    bpy.types.Object.dh_bone_sets_index = bpy.props.IntProperty(default=-1)


classes = (
    DH_BoneSetBone,
    DH_BoneSet,
    DH_OT_SaveBoneSet,
    DH_OT_LoadBoneSet,
    DH_OT_AddToBoneSet,
    DH_OT_RemoveBoneSet,
    DH_OT_UpdateBoneSet,
    DH_UL_BoneSetList,
)
