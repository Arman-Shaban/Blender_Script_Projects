
import numpy as np
import trimesh


def create_frustum(r_bottom, r_top, height, sections=64):
    """Create a tapered cylinder along the positive Z axis."""

    if r_bottom <= 0 or r_top <= 0 or height <= 0:
        raise ValueError("Radii and height must be positive.")

    theta = np.linspace(0, 2 * np.pi, sections, endpoint=False)

    # Bottom circle
    x_bottom = r_bottom * np.cos(theta)
    y_bottom = r_bottom * np.sin(theta)
    z_bottom = np.zeros_like(theta)

    # Top circle
    x_top = r_top * np.cos(theta)
    y_top = r_top * np.sin(theta)
    z_top = np.full_like(theta, height)

    # Vertices
    vertices = np.vstack([
        np.column_stack([x_bottom, y_bottom, z_bottom]),
        np.column_stack([x_top, y_top, z_top]),
        [[0, 0, 0], [0, 0, height]]
    ])

    bottom_center_idx = 2 * sections
    top_center_idx = 2 * sections + 1

    faces = []

    for i in range(sections):
        next_i = (i + 1) % sections

        # Side faces
        faces.append([i, next_i, sections + next_i])
        faces.append([i, sections + next_i, sections + i])

        # Bottom cap
        faces.append([bottom_center_idx, next_i, i])

        # Top cap
        faces.append([
            top_center_idx,
            sections + i,
            sections + next_i
        ])

    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=np.array(faces),
        process=True
    )

    mesh.fix_normals()

    return mesh


def create_ship_wheel_3d(
    num_spokes=8,
    rim_major_radius=10.0,
    rim_tube_radius=0.85,
    hub_radius=2.1,
    hub_thickness=2.2,
    inner_spoke_r1=0.55,
    inner_spoke_r2=0.38,
    outer_neck_length=1.4,
    outer_neck_r1=0.45,
    outer_neck_r2=0.55,
    knob_radius=1.55,
    resolution=64
):
    """Create a detailed 3D ship steering wheel."""

    if num_spokes < 1:
        raise ValueError("Number of spokes must be at least 1.")

    if resolution < 8:
        raise ValueError("Resolution must be at least 8.")

    meshes = []

    # 1. Main rim (Torus)
    rim = trimesh.creation.torus(
        major_radius=rim_major_radius,
        minor_radius=rim_tube_radius,
        major_sections=resolution * 2,
        minor_sections=resolution
    )

    meshes.append(rim)

    # 2. Central hub
    hub_sphere = trimesh.creation.icosphere(
        subdivisions=4,
        radius=hub_radius
    )

    scale_z = (hub_thickness / 2.0) / hub_radius

    hub_sphere.apply_scale([1.0, 1.0, scale_z])

    meshes.append(hub_sphere)

    # 3. Create spokes, outer necks, and spherical knobs
    angles = np.linspace(
        0,
        2 * np.pi,
        num_spokes,
        endpoint=False
    )

    # Rotation from Z axis to X axis
    align_x = trimesh.transformations.rotation_matrix(
        np.pi / 2,
        [0, 1, 0]
    )

    for angle in angles:

        # Rotation around Z axis
        rot_z = trimesh.transformations.rotation_matrix(
            angle,
            [0, 0, 1]
        )

        # 3A. Inner spoke
        inner_start = hub_radius * 0.7
        inner_end = rim_major_radius
        inner_length = inner_end - inner_start

        inner_spoke = create_frustum(
            r_bottom=inner_spoke_r1,
            r_top=inner_spoke_r2,
            height=inner_length,
            sections=resolution
        )

        inner_spoke.apply_transform(align_x)

        inner_spoke.apply_translation([
            inner_start, 0, 0
        ])

        inner_spoke.apply_transform(rot_z)

        meshes.append(inner_spoke)

        # 3B. Outer handle neck
        neck_start = rim_major_radius + (rim_tube_radius * 0.5)

        neck_end = (
            neck_start
            + outer_neck_length
            + (knob_radius * 0.3)
        )

        neck_length = neck_end - neck_start

        outer_neck = create_frustum(
            r_bottom=outer_neck_r1,
            r_top=outer_neck_r2,
            height=neck_length,
            sections=resolution
        )

        outer_neck.apply_transform(align_x)

        outer_neck.apply_translation([
            neck_start, 0, 0
        ])

        outer_neck.apply_transform(rot_z)

        meshes.append(outer_neck)

        # 3C. Outer spherical knob
        knob_center_x = (
            rim_major_radius
            + rim_tube_radius
            + outer_neck_length
            + (knob_radius * 0.65)
        )

        knob = trimesh.creation.icosphere(
            subdivisions=4,
            radius=knob_radius
        )

        knob.apply_translation([
            knob_center_x, 0, 0
        ])

        knob.apply_transform(rot_z)

        meshes.append(knob)

    # 4. Combine all components
    try:
        print("Performing Boolean Union...")

        combined_mesh = trimesh.boolean.union(
            meshes,
            engine="manifold"
        )

        if combined_mesh is None:
            raise RuntimeError("Boolean Union returned no mesh.")

        print("Boolean Union completed successfully.")

    except Exception as error:

        print(f"Boolean Union failed: {error}")

        print("Using standard mesh concatenation instead.")

        combined_mesh = trimesh.util.concatenate(meshes)

    return combined_mesh


# 5. Main execution
if __name__ == "__main__":

    print("Creating 3D ship steering wheel...")

    wheel_3d = create_ship_wheel_3d(
        num_spokes=8,
        resolution=64
    )

    # Export STL
    wheel_3d.export("ship_wheel_3d.stl")

    # Export OBJ
    wheel_3d.export("ship_wheel_3d.obj")

    print("3D model exported successfully!")
    print("Files:")
    print("- ship_wheel_3d.stl")
    print("- ship_wheel_3d.obj")

    # Display interactive 3D preview
    print("Opening 3D preview...")

    wheel_3d.show()
