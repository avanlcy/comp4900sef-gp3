"""Phase 7 Task 21 (spec §8.2, §8.3): the environment actors.

BP_DFDebris: one chunk of a demolished rock wall (BP_DFDestructible.Demolish spawns eight, each pushed outward): SM_DF_RockChunk
simulating physics as a PhysicsActor that ignores pawns and cars (a chunk never stops a car or the on-foot character), gone after
8 s (InitialLifeSpan); GameMode.SweepEffects removes any left at a restart.

BP_DFScatter: one actor per scatter mesh (Task 22's level builder places them): a hierarchical instanced static mesh rebuilt from
its editable Transforms (relative to the actor), solid (BlockAll) or not (NoCollision) by bBlocking, culled at CullDistance.
RebuildInstances does the work and the construction script calls it; code that spawns a scatter sets the variables and calls
RebuildInstances itself (a deferred spawn cannot be generated: Task 15).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from df import (ACTOR, BOOL, BP_DEBRIS, BP_SCATTER, COLLISION_CHANNEL, COLLISION_RESPONSE, DEBRIS_LIFE, HISM_COMP, INT,  # noqa: E402
                ISM_COMP, NAME, OBJECT, OUT, PRIMITIVE, SCATTER_CULL_CM, SM_ROCK_CHUNK, STATIC_MESH, STATIC_MESH_COMP,
                STRUCT, TRANSFORM, Blueprint, Pin, cls_ref, native_enum_pin, obj_pin, struct_ref)

S = "Dead Fire|Scatter"


def build_debris() -> Blueprint:
    bp = Blueprint(BP_DEBRIS, parent=ACTOR, description="A chunk of a demolished rock (spec §8.2): SM_DF_RockChunk simulating physics, "
                   "ignoring pawns and cars, gone after %g s." % DEBRIS_LIFE)
    bp.component("Chunk", STATIC_MESH_COMP, static_mesh=SM_ROCK_CHUNK, **{"call:set_collision_profile_name": "PhysicsActor"})
    bp.default("InitialLifeSpan", DEBRIS_LIFE)  # AActor::BeginPlay sets the life span from it
    g = bp.event_graph()
    g.section("Begin Play: a PhysicsActor that ignores pawns (the on-foot character) and cars, then simulating")
    prev = g.begin_play()
    for channel in ("ECC_Pawn", "ECC_Vehicle"):
        n = g.call_on(PRIMITIVE, "SetCollisionResponseToChannel", inputs=[native_enum_pin("Channel", COLLISION_CHANNEL, channel),
                                                                          native_enum_pin("NewResponse", COLLISION_RESPONSE, "ECR_Ignore")])
        g.link(g.var_get("Chunk", OBJECT, cls_ref(STATIC_MESH_COMP)), "Chunk", n, "self")
        g.exec(prev, n)
        prev = n
    sim = g.call_on(PRIMITIVE, "SetSimulatePhysics", inputs=[Pin("bSimulate", BOOL, default="true")])
    g.link(g.var_get("Chunk", OBJECT, cls_ref(STATIC_MESH_COMP)), "Chunk", sim, "self")
    g.exec(prev, sim)
    return bp


def build_scatter() -> Blueprint:
    bp = Blueprint(BP_SCATTER, parent=ACTOR, description="One scatter mesh (spec §8.3): a hierarchical instanced static mesh with one "
                   "instance per Transforms entry, solid when bBlocking, culled at CullDistance.")
    bp.component("Instances", HISM_COMP, **{"call:set_collision_profile_name": "NoCollision"})
    bp.variable("Mesh", "object:" + STATIC_MESH, "", S, editable=True)
    bp.variable("Transforms", "array<struct:%s>" % TRANSFORM, "", S, editable=True)  # relative to the actor
    bp.variable("bBlocking", "bool", "true", S, editable=True)
    bp.variable("CullDistance", "int", str(SCATTER_CULL_CM), S, editable=True)
    bp.default("bBlocking", True)  # rocks, wrecks and trees block; Task 22 turns it off for the flat debris
    bp.default("CullDistance", SCATTER_CULL_CM)

    g = bp.function("RebuildInstances", doc="Clears the instances, sets Mesh, the collision (BlockAll when bBlocking, else NoCollision) "
                    "and the cull distance, then adds one instance per Transforms entry (relative to the actor).")
    inst = lambda: (g.var_get("Instances", OBJECT, cls_ref(HISM_COMP)), "Instances")  # noqa: E731
    clear = g.call_on(ISM_COMP, "ClearInstances")
    g.link(*inst(), clear, "self")
    g.link_entry("then", clear, "execute")
    mesh = g.call_on(STATIC_MESH_COMP, "SetStaticMesh", inputs=[obj_pin("NewMesh", STATIC_MESH)], outputs=[Pin("ReturnValue", BOOL, "out")])
    g.link(*inst(), mesh, "self")
    g.link(g.var_get("Mesh", OBJECT, cls_ref(STATIC_MESH)), "Mesh", mesh, "NewMesh")
    g.exec(clear, mesh)
    # the profile before the instances, so each instance's body is made with it
    solid = g.branch()
    g.link(g.var_get("bBlocking", BOOL), "bBlocking", solid, "Condition")
    g.note(solid, "blocking?")
    g.exec(mesh, solid)
    cull = g.call_on(ISM_COMP, "SetCullDistances", inputs=[Pin("StartCullDistance", INT), Pin("EndCullDistance", INT)])
    g.link(*inst(), cull, "self")
    for pin in ("StartCullDistance", "EndCullDistance"):  # start = end: shown up to CullDistance, then culled (no fade band)
        g.link(g.var_get("CullDistance", INT), "CullDistance", cull, pin)
    for out, profile in (("then", "BlockAll"), ("else", "NoCollision")):
        n = g.call_on(PRIMITIVE, "SetCollisionProfileName", inputs=[Pin("InCollisionProfileName", NAME, default=profile),
                                                                    Pin("bUpdateOverlaps", BOOL, default="true")])
        g.link(*inst(), n, "self")
        g.link(solid, out, n, "execute")
        g.link(n, "then", cull, "execute")
    loop = g.for_each(Pin("e", STRUCT, sub_object=struct_ref(TRANSFORM)))
    g.link(g.var_get("Transforms", STRUCT, struct_ref(TRANSFORM), container="Array"), "Transforms", loop, "Array")
    g.link(cull, "then", loop, "Exec")
    add = g.call_on(ISM_COMP, "AddInstance", inputs=[Pin("InstanceTransform", STRUCT, sub_object=struct_ref(TRANSFORM))],
                    outputs=[Pin("ReturnValue", INT, "out")])
    g.link(*inst(), add, "self")
    g.link(loop, "Array Element", add, "InstanceTransform")
    g.link(loop, "LoopBody", add, "execute")

    ucs = bp.construction_script()
    ucs.link_entry("then", ucs.call_self("RebuildInstances"), "execute")
    return bp


def build():
    return [build_debris(), build_scatter()]


if __name__ == "__main__":
    for b in build():
        print(b.write(OUT))
