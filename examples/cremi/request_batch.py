from __future__ import print_function

import math
import numpy as np
import random

from gunpowder import *

def train():

    random.seed(42)
    set_verbose()

    affinity_neighborhood = np.array([[-1,0,0],[0,-1,0],[0,0,-1]])
    register_volume_type(VolumeType('GT_LABELS_2', interpolate=False, voxel_size=(2,2,2)))
    register_volume_type(VolumeType('GT_LABELS_4', interpolate=False, voxel_size=(4,4,4)))
    n = 35

    request = BatchRequest()
    request.add_volume_request(VolumeTypes.RAW, (84,268,268))
    request.add_volume_request(VolumeTypes.GT_LABELS, (56,56,56))
    request.add_volume_request(VolumeTypes.GT_LABELS_2, (56,56,56))
    request.add_volume_request(VolumeTypes.GT_LABELS_4, (56,56,56))
    request.add_volume_request(VolumeTypes.GT_IGNORE, (56,56,56))
    request.add_volume_request(VolumeTypes.GT_AFFINITIES, (56,56,56))
    # request.add_volume_request(VolumeTypes.LOSS_SCALE, (56,56,56))

    data_sources = tuple(
        Hdf5Source(
            sample,
            datasets = {
                VolumeTypes.RAW: 'volumes/raw',
                VolumeTypes.GT_LABELS: 'volumes/labels/neuron_ids',
            }
        ) +
        Normalize() +
        RandomLocation()
        for sample in ['sample_A_20160501.hdf','sample_B_20160501.hdf','sample_C_20160501.hdf']
    )

    artifact_source = (
        Hdf5Source(
            'sample_ABC_padded_20160501.defects.hdf',
            datasets = {
                VolumeTypes.RAW: 'defect_sections/raw',
                VolumeTypes.ALPHA_MASK: 'defect_sections/mask',
            }
        ) +
        RandomLocation(min_masked=0.05, mask_volume_type=VolumeTypes.ALPHA_MASK) +
        Snapshot(
            {
                VolumeTypes.RAW: 'volumes/raw',
            },
            every=1,
            output_filename='defect_{id}.hdf') +
        Normalize() +
        IntensityAugment(0.9, 1.1, -0.1, 0.1, z_section_wise=True) +
        ElasticAugment(
            [4,40,40],
            [0,2,2],
            [0,math.pi/2.0],
            subsample=8) +
        SimpleAugment(transpose_only_xy=True)
    )

    batch_provider_tree = (
        data_sources +
        RandomProvider() +
        ExcludeLabels([8094], ignore_mask_erode=12) +
        SplitAndRenumberSegmentationLabels() +
        ElasticAugment(
            [4,40,40],
            [0,2,2],
            [0,math.pi/2.0],
            prob_slip=0.05,
            prob_shift=0.05,
            max_misalign=25,
            subsample=8) +
        SimpleAugment(transpose_only_xy=True) +
        GrowBoundary(steps=3, only_xy=True) +
        DownSample(
            {
                VolumeTypes.GT_LABELS_2: (2, VolumeTypes.GT_LABELS),
                VolumeTypes.GT_LABELS_4: (4, VolumeTypes.GT_LABELS)
            }
        ) +
        AddGtAffinities(affinity_neighborhood) +
        IntensityAugment(0.9, 1.1, -0.1, 0.1, z_section_wise=True) +
        DefectAugment(
            prob_missing=0.03,
            prob_low_contrast=0.01,
            prob_artifact=0.03,
            artifact_source=artifact_source,
            contrast_scale=0.1) +
        ZeroOutConstSections() +
        # BalanceAffinityLabels() +
        PreCache(
            cache_size=10,
            num_workers=5) +
        Snapshot(
            {
                VolumeTypes.RAW: 'volumes/raw',
                VolumeTypes.GT_LABELS: 'volumes/labels/neuron_ids',
                VolumeTypes.GT_LABELS_2: 'volumes/labels/neuron_ids_2',
                VolumeTypes.GT_LABELS_4: 'volumes/labels/neuron_ids_4',
                VolumeTypes.GT_IGNORE: 'volumes/labels/mask',
                VolumeTypes.GT_AFFINITIES: 'volumes/labels/affinities',
            },
            every=1,
            output_filename='final_it={iteration}_id={id}.hdf') +
        PrintProfilingStats(every=n)
    )

    print("Requesting", n, "batches")

    with build(batch_provider_tree) as minibatch_maker:
        for i in range(n):
            minibatch_maker.request_batch(request)

    print("Finished")


if __name__ == "__main__":
    train()
