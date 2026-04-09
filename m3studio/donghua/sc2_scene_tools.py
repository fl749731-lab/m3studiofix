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
SC2 快速场景工具 (参考 SC2ArtTools Macros 移植):
- SC2 标准挂点批量创建 (Ref3_*, Origin, Overhead, Center, Target, ...)
- SC2 标准事件创建 (Evt_Birth, Evt_Death, Evt_Stand, ...)
- 事件重命名与合并
- Helper 可见性管理
"""

import bpy
import mathutils
from .anim_tools import get_arm_obj


# ──────────────────────────────────────────────
# SC2 标准挂点定义
# ──────────────────────────────────────────────

# SC2 中常用的标准挂点名称列表
SC2_BASE_ATTACH_POINTS = [
    'Ref_Origin',
    'Ref_Center',
    'Ref_Overhead',
    'Ref_Target',
    'Ref_Hardpoint',
    'Ref_StatusBar',
    'Ref_Origin Left',
    'Ref_Origin Right',
    'Ref_Damage',
    'Ref_Rally',
    'Ref_Weapon',
    'Ref_Shield',
    'Ref_Upgrade',
]

SC2_EVENT_TYPES = [
    ('Evt_Birth', 'Birth', '出生事件'),
    ('Evt_Stand', 'Stand', '待机事件'),
    ('Evt_Death', 'Death', '死亡事件'),
    ('Evt_Attack', 'Attack', '攻击事件'),
    ('Evt_Spell', 'Spell', '技能事件'),
    ('Evt_Walk', 'Walk', '行走事件'),
    ('Evt_Sound', 'Sound', '音效事件'),
]


# ──────────────────────────────────────────────
# 一键创建 SC2 标准挂点
# ──────────────────────────────────────────────

class DH_OT_CreateBaseAttachPoints(bpy.types.Operator):
    """批量创建 SC2 标准挂点 Empty 对象"""
    bl_idname = 'donghua.create_base_attach_points'
    bl_label = '创建标准挂点'
    bl_description = '一键创建所有 SC2 标准挂点（Ref_Origin, Ref_Center 等）'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def execute(self, context):
        arm = get_arm_obj(context)
        created = 0
        skipped = 0

        for name in SC2_BASE_ATTACH_POINTS:
            # 检查是否已存在
            existing = bpy.data.objects.get(name)
            if existing is not None:
                skipped += 1
                continue

            # 创建 Empty 对象
            empty = bpy.data.objects.new(name, None)
            empty.empty_display_type = 'ARROWS'
            empty.empty_display_size = 0.1
            context.collection.objects.link(empty)

            # 设置为骨架子对象
            empty.parent = arm
            created += 1

        self.report({'INFO'}, f'已创建 {created} 个挂点, 跳过 {skipped} 个已存在')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 自定义挂点创建
# ──────────────────────────────────────────────

class DH_OT_CreateCustomAttachPoint(bpy.types.Operator):
    """在选中骨骼位置创建自定义挂点"""
    bl_idname = 'donghua.create_custom_attach_point'
    bl_label = '在骨骼处创建挂点'
    bl_description = '在每个选中骨骼的位置创建一个 Empty 挂点并绑定'
    bl_options = {'UNDO'}

    prefix: bpy.props.StringProperty(
        name='前缀',
        default='Ref_',
        description='挂点名称前缀',
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and context.mode == 'POSE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        self.layout.prop(self, 'prefix')

    def execute(self, context):
        arm = get_arm_obj(context)
        bones = [pb for pb in arm.pose.bones if pb.bone.select]
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼')
            return {'CANCELLED'}

        created = 0
        for pb in bones:
            name = f'{self.prefix}{pb.name}'
            if bpy.data.objects.get(name):
                continue

            empty = bpy.data.objects.new(name, None)
            empty.empty_display_type = 'ARROWS'
            empty.empty_display_size = 0.08
            context.collection.objects.link(empty)

            # 父对象绑定到骨骼
            empty.parent = arm
            empty.parent_type = 'BONE'
            empty.parent_bone = pb.name
            empty.matrix_parent_inverse = (arm.matrix_world @ pb.bone.matrix_local).inverted()

            created += 1

        self.report({'INFO'}, f'已创建 {created} 个骨骼挂点')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 创建 SC2 Event 标记骨骼
# ──────────────────────────────────────────────

class DH_OT_CreateEventBone(bpy.types.Operator):
    """在骨架中创建 SC2 事件标记骨骼 (Evt_*)"""
    bl_idname = 'donghua.create_event_bone'
    bl_label = '创建事件骨骼'
    bl_description = '创建一个 SC2 标准事件标记骨骼'
    bl_options = {'UNDO'}

    event_type: bpy.props.EnumProperty(
        name='事件类型',
        items=[(e[0], e[1], e[2]) for e in SC2_EVENT_TYPES],
        default='Evt_Birth',
    )
    custom_suffix: bpy.props.StringProperty(
        name='后缀',
        default='',
        description='自定义后缀 (如 01, Left)',
    )

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'event_type')
        layout.prop(self, 'custom_suffix')

    def execute(self, context):
        arm = get_arm_obj(context)
        name = self.event_type
        if self.custom_suffix:
            name += f'_{self.custom_suffix}'

        # 检查已存在
        if arm.data.bones.get(name):
            self.report({'WARNING'}, f'骨骼 "{name}" 已存在')
            return {'CANCELLED'}

        # 需要切到编辑模式创建骨骼
        prev_mode = arm.mode
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bone = arm.data.edit_bones.new(name)
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 0.05, 0)
        edit_bone.use_deform = False  # 事件骨骼不参与变形

        bpy.ops.object.mode_set(mode=prev_mode)

        self.report({'INFO'}, f'已创建事件骨骼: {name}')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 批量重命名事件骨骼
# ──────────────────────────────────────────────

class DH_OT_RenameEventBones(bpy.types.Operator):
    """批量为选中骨骼添加/替换 Evt_ 前缀"""
    bl_idname = 'donghua.rename_event_bones'
    bl_label = '事件骨骼重命名'
    bl_description = '为选中骨骼批量添加或替换 Evt_ 前缀'
    bl_options = {'UNDO'}

    prefix: bpy.props.StringProperty(
        name='新前缀',
        default='Evt_',
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and context.mode in {'POSE', 'EDIT_ARMATURE'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=220)

    def draw(self, context):
        self.layout.prop(self, 'prefix')

    def execute(self, context):
        arm = get_arm_obj(context)
        count = 0

        if context.mode == 'POSE':
            for pb in arm.pose.bones:
                if pb.bone.select:
                    old = pb.name
                    # 移除旧前缀
                    base = old
                    if old.startswith('Evt_'):
                        base = old[4:]
                    elif old.startswith('Ref_'):
                        base = old[4:]
                    pb.name = f'{self.prefix}{base}'
                    count += 1
        elif context.mode == 'EDIT_ARMATURE':
            for eb in arm.data.edit_bones:
                if eb.select:
                    old = eb.name
                    base = old
                    if old.startswith('Evt_'):
                        base = old[4:]
                    elif old.startswith('Ref_'):
                        base = old[4:]
                    eb.name = f'{self.prefix}{base}'
                    count += 1

        self.report({'INFO'}, f'已重命名 {count} 个骨骼 (前缀: {self.prefix})')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 合并重复事件骨骼
# ──────────────────────────────────────────────

class DH_OT_CombineDuplicateEvents(bpy.types.Operator):
    """合并同名/同类型的事件骨骼的关键帧到单个骨骼"""
    bl_idname = 'donghua.combine_duplicate_events'
    bl_label = '合并重复事件'
    bl_description = '将相同前缀的事件骨骼的关键帧合并到单个骨骼上'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm and arm.animation_data and arm.animation_data.action

    def execute(self, context):
        arm = get_arm_obj(context)
        action = arm.animation_data.action

        # 找到所有 Evt_ 骨骼
        event_bones = [b for b in arm.data.bones if b.name.startswith('Evt_')]
        if len(event_bones) < 2:
            self.report({'INFO'}, '没有足够的事件骨骼需要合并')
            return {'CANCELLED'}

        # 按基础名称分组 (去掉末尾数字)
        groups = {}
        for b in event_bones:
            # Evt_Birth_01, Evt_Birth_02 → Evt_Birth
            base = b.name.rstrip('0123456789_ ')
            if not base:
                base = b.name
            if base not in groups:
                groups[base] = []
            groups[base].append(b.name)

        merged = 0
        for base, names in groups.items():
            if len(names) < 2:
                continue
            # 以第一个为目标
            target = names[0]
            for source in names[1:]:
                # 合并 F-Curve 关键帧
                for fc in list(action.fcurves):
                    if f'pose.bones["{source}"]' in fc.data_path:
                        new_path = fc.data_path.replace(
                            f'pose.bones["{source}"]',
                            f'pose.bones["{target}"]'
                        )
                        # 查找或创建目标 F-Curve
                        target_fc = action.fcurves.find(new_path, index=fc.array_index)
                        if target_fc is None:
                            target_fc = action.fcurves.new(new_path, index=fc.array_index)

                        # 复制关键帧
                        for kp in fc.keyframe_points:
                            target_fc.keyframe_points.insert(kp.co[0], kp.co[1])

                        # 删除源 F-Curve
                        action.fcurves.remove(fc)

                merged += 1

        self.report({'INFO'}, f'已合并 {merged} 个重复事件骨骼的关键帧')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# M3 辅助绘制开关 (直接切换 m3_options 属性)
# ──────────────────────────────────────────────

class DH_OT_ToggleHelperVisibility(bpy.types.Operator):
    """切换 M3 辅助绘制的显示/隐藏（挂点/碰撞体/灯光/粒子等）"""
    bl_idname = 'donghua.toggle_helper_vis'
    bl_label = '切换辅助项显示'
    bl_description = '直接切换 M3 对象的 3D 视口辅助绘制开关'
    bl_options = {'UNDO'}

    helper_type: bpy.props.EnumProperty(
        name='类型',
        items=[
            ('ATTACH', '挂点', '切换挂点/挂点体积的 3D 绘制'),
            ('HITTEST', '碰撞体', '切换碰撞体的 3D 绘制'),
            ('PARTICLES', '粒子/力场', '切换粒子和力场的 3D 绘制'),
            ('ALL', '全部辅助', '切换所有 M3 辅助绘制'),
        ],
    )

    @classmethod
    def poll(cls, context):
        arm = get_arm_obj(context)
        return arm is not None and hasattr(arm, 'm3_options')

    def execute(self, context):
        arm = get_arm_obj(context)
        opts = arm.m3_options

        if self.helper_type == 'ATTACH':
            new_val = not opts.draw_attach_points
            opts.draw_attach_points = new_val
            opts.draw_attach_volumes = new_val
            state = '显示' if new_val else '隐藏'
            self.report({'INFO'}, f'挂点绘制: {state}')

        elif self.helper_type == 'HITTEST':
            new_val = not opts.draw_hittests
            opts.draw_hittests = new_val
            opts.draw_rigidbodies = new_val
            state = '显示' if new_val else '隐藏'
            self.report({'INFO'}, f'碰撞体/刚体绘制: {state}')

        elif self.helper_type == 'PARTICLES':
            new_val = not opts.draw_particles
            opts.draw_particles = new_val
            opts.draw_forces = new_val
            opts.draw_ribbons = new_val
            state = '显示' if new_val else '隐藏'
            self.report({'INFO'}, f'粒子/力场/飘带绘制: {state}')

        elif self.helper_type == 'ALL':
            # 检查当前是否大部分打开
            props = [
                'draw_attach_points', 'draw_attach_volumes', 'draw_hittests',
                'draw_lights', 'draw_particles', 'draw_ribbons',
                'draw_projections', 'draw_forces', 'draw_cameras',
                'draw_rigidbodies', 'draw_clothconstraints', 'draw_ikjoints',
                'draw_shadowboxes', 'draw_warps', 'draw_turrets',
            ]
            on_count = sum(1 for p in props if getattr(opts, p))
            new_val = on_count < len(props) // 2  # 多数关闭则打开，多数打开则关闭
            for p in props:
                setattr(opts, p, new_val)
            state = '全部显示' if new_val else '全部隐藏'
            self.report({'INFO'}, f'M3 辅助绘制: {state}')

        # 强制刷新视口
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}


def register_props():
    pass


classes = (
    DH_OT_CreateBaseAttachPoints,
    DH_OT_CreateCustomAttachPoint,
    DH_OT_CreateEventBone,
    DH_OT_RenameEventBones,
    DH_OT_CombineDuplicateEvents,
    DH_OT_ToggleHelperVisibility,
)
