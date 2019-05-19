import bmesh
from bmesh.types import BMEdge

from ..fill import fill_panel, fill_glass_panes, fill_louver
from ...utils import (
    split,
    split_quad,
    filter_geom,
    face_with_verts,
    calc_edge_median,
    calc_face_dimensions,
    filter_vertical_edges,
    filter_horizontal_edges,
)


def create_door(bm, faces, prop):
    """Create basic flush door

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        faces (list): selected faces
        prop (bpy.types.PropertyGroup): DoorProperty
    """

    for face in faces:
        face = create_door_split(bm, face, prop.size_offset)
        # -- check that split was successful
        if not face:
            continue

        nfaces = create_door_double(bm, face, prop)
        for face in nfaces:
            face = create_door_frame(bm, face, prop)
            create_door_fill(bm, face, prop)


def create_door_split(bm, face, prop):
    """Use properties from SplitOffset to subdivide face into regular quads

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to make split (must be quad)
        prop (bpy.types.PropertyGroup): SizeOffsetProperty

    Returns:
        bmesh.types.BMFace: New face created after split
    """
    size, off = prop.size, prop.offset
    return split(bm, face, size.y, size.x, off.x, off.y, off.z)


def create_door_frame(bm, face, prop):
    """Create extrude and inset around a face to make door frame

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to make frame for
        prop (bpy.types.PropertyGroup): DoorProperty

    Returns:
        bmesh.types.BMFace: face after frame is created
    """

    # Frame outset
    face = extrude_face_and_delete_bottom(bm, face, prop.frame_depth)

    if prop.frame_thickness > 0:
        w = calc_face_dimensions(face)[0]
        off = (w / 3) - prop.frame_thickness
        edges = split_face_vertical_with_offset(bm, face, 2, [off, off])

        top_edge = split_edges_horizontal_offset_top(bm, edges, prop.frame_thickness)[
            -1
        ]
        face = min(top_edge.link_faces, key=lambda f: f.calc_center_median().z)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if prop.frame_depth:
        f = extrude_face_and_delete_bottom(bm, face, -prop.frame_depth)
        return f
    return face


def create_door_double(bm, face, prop):
    """Split face vertically into two faces

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to operate on
        prop (bpy.types.PropertyGroup): DoorProperty

    Returns:
        list: face(s) after double door created
    """
    if prop.has_double_door:
        ret = bmesh.ops.subdivide_edges(
            bm, edges=filter_horizontal_edges(face.edges, face.normal), cuts=1
        ).get("geom_inner")

        return list(filter_geom(ret, BMEdge)[-1].link_faces)
    return [face]


def create_door_fill(bm, face, prop):
    """Create extra elements on face

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to operate on
        prop (bpy.types.PropertyGroup): DoorProperty
    """
    if prop.fill_type == "NONE":
        pass
    elif prop.fill_type == "PANELS":
        fill_panel(bm, face, prop.panel_fill)
    elif prop.fill_type == "GLASS PANES":
        fill_glass_panes(bm, face, prop.glass_fill)
    elif prop.fill_type == "LOUVER":
        fill_louver(bm, face, prop.louver_fill)


def delete_bottom_face(bm, face):
    """delete a face that is hidden at the bottom of face

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face that has hidden face at the bottom
    """
    bottom_edge = min(
        filter_horizontal_edges(face.edges, face.normal),
        key=lambda e: calc_edge_median(e).z,
    )
    hidden = min(
        [f for f in bottom_edge.link_faces], key=lambda f: f.calc_center_median().z
    )
    bmesh.ops.delete(bm, geom=[hidden], context="FACES")


def extrude_face_and_delete_bottom(bm, face, extrude_depth):
    """extrude a face, and delete another face hidden at the bottom of the extrusion

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to extrude
        extrude_depth (float):

    Returns:
        bmesh.types.BMFace: new face from extrusion
    """
    f = bmesh.ops.extrude_discrete_faces(bm, faces=[face]).get("faces")[-1]
    bmesh.ops.translate(bm, verts=f.verts, vec=f.normal * extrude_depth)
    delete_bottom_face(bm, f)
    return f


def split_face_vertical_with_offset(bm, face, cuts, offsets):
    """split a face(quad) vertically and move the new edges

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        face (bmesh.types.BMFace): face to split
        cuts (int): number of splits
        offsets (float): how far from the edges splits are

    Returns:
        list: new edges from split
    """
    median = face.calc_center_median()
    res = split_quad(bm, face, True, cuts)
    edges = filter_geom(res["geom_inner"], BMEdge)
    edges.sort(
        key=lambda e: getattr(calc_edge_median(e), "x" if face.normal.y else "y")
    )

    for off, e in zip(offsets, edges):
        tvec = calc_edge_median(e) - median
        bmesh.ops.translate(bm, verts=e.verts, vec=tvec.normalized() * off)
    return edges


def split_edges_horizontal_offset_top(bm, edges, offset):
    """split a face(quad) horizontally and move the new edge

    Args:
        bm (bmesh.types.BMesh): bmesh of editmode object
        edges (TYPE): Description
        offset (TYPE): Description

    Returns:
        bmesh.types.BMEdge: edge created during split
    """
    face = face_with_verts(bm, list({v for e in edges for v in e.verts}))
    v_edges = filter_vertical_edges(face.edges, face.normal)
    new_verts = []
    for e in v_edges:
        vert = max(list(e.verts), key=lambda v: v.co.z)
        v = bmesh.utils.edge_split(e, vert, offset / e.calc_length())[-1]
        new_verts.append(v)

    res = bmesh.ops.connect_verts(bm, verts=new_verts).get("edges")
    return res
