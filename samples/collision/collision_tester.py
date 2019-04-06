#!/usr/bin/env python

import sys

from panda3d.core import KeyboardButton
from panda3d.core import MouseButton
from panda3d.core import Point2
from panda3d.core import Point3
from panda3d.core import TextNode
from panda3d.core import CollisionNode
from panda3d.core import CollisionTraverser
from panda3d.core import CollisionHandlerQueue
from panda3d.core import Plane
#from panda3d.core import Parabolaf
from panda3d.core import CollisionBox
from panda3d.core import CollisionCapsule
from panda3d.core import CollisionFloorMesh
from panda3d.core import CollisionInvSphere
from panda3d.core import CollisionLine
from panda3d.core import CollisionParabola
from panda3d.core import CollisionPlane
from panda3d.core import CollisionPolygon
from panda3d.core import CollisionRay
from panda3d.core import CollisionSegment
from panda3d.core import CollisionSphere
from panda3d.core import CollisionTube

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import OnscreenText


def hint_text(text, i):
    return OnscreenText(
        text=text, pos=(0.06, -.06 * (i + 0.5)), fg=(1, 1, 1, 1),
        parent=base.a2dTopLeft,align=TextNode.ALeft, scale=.05,
    )

class ColliderSolid:
    def __init__(self, name, solid, cam_shot=False, origin=True):
        self.name = name
        self.solid = solid
        self.cam_shot = cam_shot
        self.origin = origin

    def repr(self):
        return self.name


solids_into = [
    ColliderSolid("Sphere", CollisionSphere((0, 0, 0), 1.5)),
    ColliderSolid("Capsule", CollisionCapsule((-1, 0, 0), (1, 0, 0), 1)),
    ColliderSolid("Box", CollisionBox((-1, -1, -1), (1, 1, 1))),
    ColliderSolid("Plane", CollisionPlane(Plane((0, 0, 1), (0, 0, 0)))),
    ColliderSolid("InvSphere", CollisionInvSphere((0, 0, 0), 2)),
]
solids_from = [
    ColliderSolid(
        "Sphere",
        CollisionSphere((0, 0, 0), 1.5),
    ),
    ColliderSolid(
        "Box",
        CollisionBox((-1, -1, -1), (1, 1, 1)),
    ),
    ColliderSolid(
        "Capsule",
        CollisionCapsule((-1, 0, 0), (1, 0, 0), 1),
    ),
    ColliderSolid(
        "Segment",
        CollisionSegment((0, 0, 0), (0, 25, 0)),
        cam_shot=True, origin=False,
    ),
    ColliderSolid(
        "Ray",
        CollisionRay((0, 0, 0), (0, 1, 0)),
        cam_shot=True, origin=False,
    ),
    ColliderSolid(
        "Line",
        CollisionLine((0, 0, 0), (0, 1, 0)),
        cam_shot=True, origin=False,
    ),
]


class Base(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        base.disableMouse()
        self.accept("escape", sys.exit)

        # Camera
        self.camera_gimbal = base.render.attach_new_node("Camera gimbal")
        base.camera.reparent_to(self.camera_gimbal)
        base.camera.set_pos(0, -10, 0)
        self.rotation_mode = False
        self.mouse_pos = None
        self.accept("mouse3", self.set_rotation_mode, [True])
        self.accept("mouse3-up", self.set_rotation_mode, [False])
        self.accept("wheel_up", self.move_camera_distance, [-1])
        self.accept("wheel_down", self.move_camera_distance, [1])
        base.taskMgr.add(self.move_camera, "Move camera", sort=10)

        self.hint_from = hint_text("", 1)
        self.hint_into = hint_text("", 2)
        self.hint_lmb = hint_text("LMB: Shoot / move From solid", 3)
        self.hint_rmb = hint_text("RMB: Move camera", 4)
        self.hint_mmb = hint_text("MMB: Rotate From CollisionSolid", 5)
        self.hint_wheel = hint_text("Mouse wheel: Zoom in / out", 6)
        self.solid_texts = [self.hint_from, self.hint_into]
        self.accept(
            "update-from-text",
            self.update_solid_text,
            [0, "1: Change From solid ({})"],
        )
        self.accept(
            "update-into-text",
            self.update_solid_text,
            [1, "2: Change Into solid ({})"],
        )

        self.from_coll = FromCollider(solids_from)
        self.accept("1", self.from_coll.switch_solid)
        self.into_coll = IntoCollider(solids_into)
        self.accept("2", self.into_coll.switch_solid)

    def update_solid_text(self, idx, hint_text, solid_repr):
        self.solid_texts[idx].setText(hint_text.format(solid_repr))

    def set_rotation_mode(self, mode):
        self.rotation_mode = mode
        if base.mouseWatcherNode.has_mouse():
            self.mouse_pos = base.mouseWatcherNode.get_mouse()

    def move_camera_distance(self, direction):
        base.camera.set_pos(base.camera.get_pos() * (1 + 0.1 * direction))

    def move_camera(self, task):
        rot = globalClock.get_dt() * 360.0 / 3.0
        up_down = 0
        left_right = 0
        if base.mouseWatcherNode.is_button_down(KeyboardButton.up()):
            up_down -= 1
        if base.mouseWatcherNode.is_button_down(KeyboardButton.down()):
            up_down += 1
        if base.mouseWatcherNode.is_button_down(KeyboardButton.left()):
            left_right -=1
        if base.mouseWatcherNode.is_button_down(KeyboardButton.right()):
            left_right +=1
        if self.rotation_mode and base.mouseWatcherNode.has_mouse():
            mouse_pos = base.mouseWatcherNode.get_mouse()
            mouse_delta = mouse_pos - self.mouse_pos
            self.mouse_pos = Point2(mouse_pos)
            up_down += mouse_delta.get_y() * 50
            left_right += mouse_delta.get_x() * -50
        self.camera_gimbal.set_h(self.camera_gimbal.get_h() + left_right * rot)
        new_pitch = self.camera_gimbal.get_p() + up_down * rot
        self.camera_gimbal.set_p(min(max(new_pitch, -89), 89))
        return task.cont


class Collider:
    def __init__(self, solids):
        self.solids = solids
        self.solid_idx = 0

        self.np = base.render.attach_new_node("from")
        self.model = base.loader.load_model("models/zup-axis")
        self.model.reparent_to(self.np)
        self.model.set_scale(0.1)
        if not self.solids[self.solid_idx].origin:
            self.model.hide()
        self.coll = CollisionNode("coll")
        self.coll_np = self.np.attach_new_node(self.coll)
        self.coll_np.show()
        self.coll.add_solid(self.solids[self.solid_idx].solid)

    def switch_solid(self):
        self.coll.remove_solid(0)
        self.solid_idx = (self.solid_idx + 1) % len(self.solids)
        self.coll.add_solid(self.solids[self.solid_idx].solid)
        if self.solids[self.solid_idx].origin:
            self.model.show()
        else:
            self.model.hide()


class FromCollider(Collider):
    def __init__(self, solids):
        Collider.__init__(self, solids)
        self.coll.set_into_collide_mask(0)

        self.traverser = CollisionTraverser("traverser")
        self.traverser.show_collisions(base.render)
        self.queue = CollisionHandlerQueue()
        self.traverser.add_collider(self.coll_np, self.queue)
        base.task_mgr.add(self.collide, "collide", sort=15)
        base.task_mgr.add(self.adjust_solid_pos, "adjust solid pos", sort=10)
        base.messenger.send(
            "update-from-text",
            [self.solids[self.solid_idx].name],
        )

        if base.mouseWatcherNode.has_mouse():
            self.last_mpos = Point2(base.mouseWatcherNode.get_mouse())
        else:
            self.last_mpos = None

    def adjust_solid_pos(self, task):
        if base.mouseWatcherNode.has_mouse():
            lmb = base.mouseWatcherNode.is_button_down(MouseButton.one())
            mmb = base.mouseWatcherNode.is_button_down(MouseButton.two())
            mpos = Point2(base.mouseWatcherNode.get_mouse())

            if lmb and self.solids[self.solid_idx].cam_shot:
                self.np.reparent_to(base.cam)
                self.np.set_pos(0, 0, 0)
                mpos_d = Point3(mpos.x, mpos.y, 0)
                cam_space_vec = Point3()
                base.cam.node().get_lens().extrude_depth(mpos_d, cam_space_vec)
                cam_space_vec /= cam_space_vec.length()
                self.np.look_at(cam_space_vec)
                self.np.wrt_reparent_to(base.render)
            elif lmb and not self.solids[self.solid_idx].cam_shot:
                model_pos = self.np.get_pos(base.cam)
                frustum_pos = Point3()
                base.cam.node().get_lens().project(model_pos, frustum_pos)
                mouse_x = mpos.x
                mouse_y = mpos.y
                model_depth = frustum_pos[2]
                new_frustum_pos = Point3(mpos.x, mpos.y, model_depth)
                new_model_pos = Point3()
                base.cam.node().get_lens().extrude_depth(
                    new_frustum_pos,
                    new_model_pos,
                )
                self.np.set_pos(base.cam, new_model_pos)

            if mmb and self.last_mpos is not None:
                mpos_delta = mpos - self.last_mpos
                hpr_delta = Point3(mpos_delta.x * 180, mpos_delta.y * 180, 0)
                self.np.set_hpr(base.cam, self.np.get_hpr(base.cam) + hpr_delta)
            self.last_mpos = mpos
        return task.cont

    def switch_solid(self):
        was_cam_shot = self.solids[self.solid_idx].cam_shot
        super().switch_solid()
        is_cam_shot = self.solids[self.solid_idx].cam_shot
        if was_cam_shot and not is_cam_shot:
            self.np.set_pos(self.np.get_pos() / 2)
        base.messenger.send(
            "update-from-text",
            [self.solids[self.solid_idx].name],
        )

    def collide(self, task):
        self.traverser.traverse(base.render)
        return task.cont


class IntoCollider(Collider):
    def __init__(self, solids):
        Collider.__init__(self, solids)
        self.coll.set_from_collide_mask(0)
        base.messenger.send(
            "update-into-text",
            [self.solids[self.solid_idx].name],
        )
        #base.task_mgr.add(self.wobble, "wobble")

    def wobble(self, task):
        if self.wobble_type == STILL:
            pass
        elif self.wobble_type == LEFTRIGHT:
            self.np.set_x(sin((task.time*2*pi)/10) * 5)
        elif self.wobble_type == ROTATE:
            self.np.set_hpr(
                task.time*360/10,
                task.time*360/20,
                task.time*360/30,
            )
        return task.cont

    def switch_solid(self):
        super().switch_solid()
        base.messenger.send(
            "update-into-text",
            [self.solids[self.solid_idx].name],
        )


if __name__ == '__main__':
    app = Base()
    app.run()