# ------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# ------------------------------------------------------------------------------

from __future__ import division
import torch
import numpy as np


def unfold_camera_param(camera, device=None):
    R = torch.as_tensor(camera['R'], dtype=torch.float, device=device)
    T = torch.as_tensor(camera['T'], dtype=torch.float, device=device)
    fx = torch.as_tensor(camera['fx'], dtype=torch.float, device=device)
    fy = torch.as_tensor(camera['fy'], dtype=torch.float, device=device)
    f = torch.tensor([fx, fy], dtype=torch.float, device=device).reshape(2, 1)
    c = torch.as_tensor(
        [[camera['cx']], [camera['cy']]],
        dtype=torch.float,
        device=device)
    k = torch.as_tensor(camera['k'], dtype=torch.float, device=device)
    p = torch.as_tensor(camera['p'], dtype=torch.float, device=device)
    return R, T, f, c, k, p

def project_point_radial(x, R, T, K):
    n = x.shape[0]
    x = x
    # world2camera
    # https://www-users.cs.umn.edu/~hspark/CSci5980/Lec2_ProjectionMatrix.pdf
    xcam = torch.mm(R, torch.t(x)) - T
    xcam = torch.mm(K, xcam)

    ypixel = xcam[:2] / (xcam[2]+1e-5)
    return torch.t(ypixel)


def _project_point_radial(x, R, T, f, c, k, p):
    """
    Args
        x: Nx3 points in world coordinates
        R: 3x3 Camera rotation matrix
        T: 3x1 Camera translation parameters
        f: (scalar) Camera focal length
        c: 2x1 Camera center
        k: 3x1 Camera radial distortion coefficients
        p: 2x1 Camera tangential distortion coefficients
    Returns
        ypixel.T: Nx2 points in pixel space
    """
    n = x.shape[0]
    xcam = torch.mm(R, torch.t(x) - T)
    y = xcam[:2] / (xcam[2] + 1e-5)

    kexp = k.repeat((1, n))
    r2 = torch.sum(y**2, 0, keepdim=True)
    r2exp = torch.cat([r2, r2**2, r2**3], 0)
    radial = 1 + torch.einsum('ij,ij->j', kexp, r2exp)

    tan = p[0] * y[1] + p[1] * y[0]
    corr = (radial + 2 * tan).repeat((2, 1))

    y = y * corr + torch.ger(torch.cat([p[1], p[0]]).view(-1), r2.view(-1))
    ypixel = (f * y) + c
    return torch.t(ypixel)


def project_pose(x, camera, holistic=False):
    R, T, f, c, k, p = unfold_camera_param(camera, device=x.device)
    # Voxelpose uses world2camera with subtraction
    # as opposed to addition
    if holistic:
        K = torch.tensor([f[0][0], 0, c[0][0],
                         0, f[1][0], c[1][0],
                         0, 0, 1],
                         dtype=torch.float, device=x.device)
        K = K.reshape(3, 3)
        return project_point_radial(x, R, T, K)
    else:
        return _project_point_radial(x, R, T, f, c, k, p)


def world_to_camera_frame(x, R, T):
    """
    Args
        x: Nx3 3d points in world coordinates
        R: 3x3 Camera rotation matrix
        T: 3x1 Camera translation parameters
    Returns
        xcam: Nx3 3d points in camera coordinates
    """

    R = torch.as_tensor(R, device=x.device)
    T = torch.as_tensor(T, device=x.device)
    xcam = torch.mm(R, torch.t(x) - T)
    return torch.t(xcam)


def camera_to_world_frame(x, R, T):
    """
    Args
        x: Nx3 points in camera coordinates
        R: 3x3 Camera rotation matrix
        T: 3x1 Camera translation parameters
    Returns
        xcam: Nx3 points in world coordinates
    """

    R = torch.as_tensor(R, device=x.device)
    T = torch.as_tensor(T, device=x.device)
    xcam = torch.mm(torch.t(R), torch.t(x))
    xcam = xcam + T  # rotate and translate
    return torch.t(xcam)
