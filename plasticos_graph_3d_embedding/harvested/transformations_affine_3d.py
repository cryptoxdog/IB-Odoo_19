3D Affine Transformation Operators for CompoundE3D

Implements 5 geometric transformations in homogeneous coordinates:
1. Translation (T): SE(3) - entity displacement
2. Scaling (S): Aff(3) - magnitude modulation
3. Rotation (R): SO(3) - yaw/pitch/roll (non-commutative)
4. Reflection (F): SO(3) - Householder reflection
5. Shear (H): Aff(3) - directional distortion

All operators work on 4D homogeneous coordinates: [x, y, z, 1]
"""

import numpy as np
import torch
from typing import Tuple, Union


class AffineOperator3D:
    """3D affine transformation operators in homogeneous coordinates."""

    @staticmethod
    def translation(v: Union[np.ndarray, torch.Tensor], backend="numpy") -> Union[np.ndarray, torch.Tensor]:
        """
        Translation operator T ∈ SE(3).

        Args:
            v: Translation vector (3D)
            backend: 'numpy' or 'torch'

        Returns:
            4x4 transformation matrix
        """
        if backend == "torch":
            assert isinstance(v, torch.Tensor), "v must be torch.Tensor for torch backend"
            assert v.shape[-1] == 3, "Translation vector must be 3D"
            T = torch.eye(4, device=v.device, dtype=v.dtype)
            T[:3, 3] = v
            return T
        else:
            v = np.asarray(v)
            assert v.shape == (3,), "Translation vector must be 3D"
            T = np.eye(4)
            T[:3, 3] = v
            return T

    @staticmethod
    def scaling(s: Union[np.ndarray, torch.Tensor], backend="numpy") -> Union[np.ndarray, torch.Tensor]:
        """
        Scaling operator S ∈ Aff(3).

        Args:
            s: Scaling factors (3D)
            backend: 'numpy' or 'torch'

        Returns:
            4x4 transformation matrix
        """
        if backend == "torch":
            assert isinstance(s, torch.Tensor), "s must be torch.Tensor for torch backend"
            assert s.shape[-1] == 3, "Scaling vector must be 3D"
            S = torch.diag(torch.cat([s, torch.ones(1, device=s.device, dtype=s.dtype)]))
            return S
        else:
            s = np.asarray(s)
            assert s.shape == (3,), "Scaling vector must be 3D"
            S = np.diag([s, s, s, 1.0])[^2][^3]
            return S

    @staticmethod
    def rotation(yaw: float, pitch: float, roll: float, backend="numpy") -> Union[np.ndarray, torch.Tensor]:
        """
        3D rotation operator R = Rz(yaw)·Ry(pitch)·Rx(roll) ∈ SO(3).
        Non-commutative: order matters!

        Args:
            yaw: Rotation around Z-axis (radians)
            pitch: Rotation around Y-axis (radians)
            roll: Rotation around X-axis (radians)
            backend: 'numpy' or 'torch'

        Returns:
            4x4 transformation matrix
        """
        if backend == "torch":
            device = torch.device("cpu")  # Default, will be moved to correct device by caller

            # Yaw (Z-axis)
            Rz = torch.tensor([
                [torch.cos(torch.tensor(yaw)), -torch.sin(torch.tensor(yaw)), 0, 0],
                [torch.sin(torch.tensor(yaw)), torch.cos(torch.tensor(yaw)), 0, 0],
               ,[^2]
[^2]
            ], device=device, dtype=torch.float32)

            # Pitch (Y-axis)
            Ry = torch.tensor([
                [torch.cos(torch.tensor(pitch)), 0, -torch.sin(torch.tensor(pitch)), 0],
               ,[^2]
                [torch.sin(torch.tensor(pitch)), 0, torch.cos(torch.tensor(pitch)), 0],
[^2]
            ], device=device, dtype=torch.float32)

            # Roll (X-axis)
            Rx = torch.tensor([
               ,[^2]
                [0, torch.cos(torch.tensor(roll)), -torch.sin(torch.tensor(roll)), 0],
                [0, torch.sin(torch.tensor(roll)), torch.cos(torch.tensor(roll)), 0],
[^2]
            ], device=device, dtype=torch.float32)

            return Rz @ Ry @ Rx
        else:
            # Yaw (Z-axis)
            Rz = np.array([
                [np.cos(yaw), -np.sin(yaw), 0, 0],
                [np.sin(yaw), np.cos(yaw), 0, 0],
               ,[^2]
[^2]
            ])

            # Pitch (Y-axis)
            Ry = np.array([
                [np.cos(pitch), 0, -np.sin(pitch), 0],
               ,[^2]
                [np.sin(pitch), 0, np.cos(pitch), 0],
[^2]
            ])

            # Roll (X-axis)
            Rx = np.array([
               ,[^2]
                [0, np.cos(roll), -np.sin(roll), 0],
                [0, np.sin(roll), np.cos(roll), 0],
[^2]
            ])

            return Rz @ Ry @ Rx

    @staticmethod
    def reflection(n: Union[np.ndarray, torch.Tensor], backend="numpy") -> Union[np.ndarray, torch.Tensor]:
        """
        Householder reflection F = I - 2nn^T ∈ SO(3).
        Reflects across hyperplane with normal vector n.

        Args:
            n: Unit normal vector (3D)
            backend: 'numpy' or 'torch'

        Returns:
            4x4 transformation matrix
        """
        if backend == "torch":
            assert isinstance(n, torch.Tensor), "n must be torch.Tensor for torch backend"
            assert n.shape[-1] == 3, "Normal vector must be 3D"
            n = n / torch.norm(n)  # Normalize
            F = torch.eye(4, device=n.device, dtype=n.dtype)
            F[:3, :3] = torch.eye(3, device=n.device) - 2 * torch.outer(n, n)
            return F
        else:
            n = np.asarray(n)
            assert n.shape == (3,), "Normal vector must be 3D"
            n = n / np.linalg.norm(n)  # Normalize
            F = np.eye(4)
            F[:3, :3] = np.eye(3) - 2 * np.outer(n, n)
            return F

    @staticmethod
    def shear(sh: Tuple[float, ...], backend="numpy") -> Union[np.ndarray, torch.Tensor]:
        """
        Shear operator H ∈ Aff(3) with 6 parameters.

        Args:
            sh: Tuple of 6 shear parameters (Shx_y, Shx_z, Shy_x, Shy_z, Shz_x, Shz_y)
            backend: 'numpy' or 'torch'

        Returns:
            4x4 transformation matrix
        """
        assert len(sh) == 6, "Shear requires 6 parameters"

        if backend == "torch":
            device = torch.device("cpu")  # Will be moved by caller
            H = torch.tensor([
                [1, sh, sh, 0],[^3][^4]
                [sh, 1, sh, 0],[^5]
                [sh, sh, 1, 0],[^6][^2]
[^2]
            ], device=device, dtype=torch.float32)
            return H
        else:
            H = np.array([
                [1, sh, sh, 0],[^4][^3]
                [sh, 1, sh, 0],[^5]
                [sh, sh, 1, 0],[^6][^2]
[^2]
            ])
            return H

    @staticmethod
    def compose(*operators: Union[np.ndarray, torch.Tensor]) -> Union[np.ndarray, torch.Tensor]:
        """
        Compose multiple transformation matrices via matrix multiplication.
        Order matters: compose(A, B, C) = A · B · C (right-to-left application)

        Args:
            *operators: Variable number of 4x4 transformation matrices

        Returns:
            Composed 4x4 transformation matrix
        """
        if len(operators) == 0:
            raise ValueError("At least one operator required")

        result = operators
        for op in operators[1:]:
            if isinstance(result, torch.Tensor):
                result = result @ op
            else:
                result = result @ op
