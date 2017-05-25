import logging
import numpy as np
from scipy.ndimage.morphology import distance_transform_edt

from .batch_filter import BatchFilter
from gunpowder.volume import Volume, VolumeType

logger = logging.getLogger(__name__)

class ExcludeLabels(BatchFilter):
    '''Excludes several labels from the ground-truth.

    The labels will be replaced by background_value. The GT_IGNORE mask will be 
    set to 0 for the excluded locations that are further than ignore_mask_erode 
    away from not excluded locations.
    '''

    def __init__(self, labels, ignore_mask_erode, background_value=0):
        '''
        Args:
            labels: List of IDs to exclude from the ground-truth.
            ignore_mask_erode: By how much (in world units) to erode the ignore mask.
            background_value: Value to replace excluded IDs.
        '''
        self.labels = set(labels)
        self.ignore_mask_erode = ignore_mask_erode
        self.background_value = background_value

    def prepare(self, request):

        assert VolumeType.GT_IGNORE in request.volumes, "If you use ExcludeLabels, you need to request VolumeType.GT_IGNORE."

        # we add it, don't request upstream
        del request.volumes[VolumeType.GT_IGNORE]

    def process(self, batch, request):

        gt = batch.volumes[VolumeType.GT_LABELS]

        # 0 marks included regions (to be used directly with distance transform 
        # later)
        include_mask = np.ones(gt.data.shape)

        gt_labels = np.unique(gt.data)
        logger.debug("batch contains GT labels: " + str(gt_labels))
        for label in gt_labels:
            if label in self.labels:
                logger.debug("excluding label " + str(label))
                gt.data[gt.data==label] = self.background_value
            else:
                include_mask[gt.data==label] = 0

        distance_to_include = distance_transform_edt(include_mask, sampling=gt.resolution)
        logger.debug("max distance to foreground is " + str(distance_to_include.max()))

        # 1 marks included regions, plus a context area around them
        include_mask = distance_to_include<self.ignore_mask_erode

        # include mask was computed on GT_LABELS ROI, we need to crop to 
        # requested GT_IGNORE ROI
        gt_ignore_roi = request.volumes[VolumeType.GT_IGNORE]
        crop_roi = gt.roi.intersect(gt_ignore_roi)
        crop_roi_in_gt = (crop_roi - gt.roi.get_offset()).get_bounding_box()
        include_mask = include_mask[crop_roi_in_gt]

        batch.volumes[VolumeType.GT_IGNORE] = Volume(include_mask, gt_ignore_roi, gt.resolution, interpolate=False)
