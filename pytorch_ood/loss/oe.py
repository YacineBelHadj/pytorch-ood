import logging

import torch
from torch import nn

from pytorch_ood.utils import contains_unknown, is_unknown

from .crossentropy import cross_entropy

log = logging.getLogger(__name__)


class OutlierExposureLoss(nn.Module):
    """
    From the paper *Deep Anomaly Detection With Outlier Exposure*.

    The loss for OOD samples is the cross-entropy between the predicted distribution and the uniform distribution.

    .. math:: \\sum_{x,y \\in \\mathcal{D}^{in}} \\mathcal{L}_{NLL}(f(x),y) + \\alpha
        \\sum_{x \\in \\mathcal{D}^{out}} D_{KL}(f(x) \\Vert \\mathcal{U})

    :see Paper: https://arxiv.org/pdf/1812.04606v1.pdf
    """

    def __init__(self, alpha=0.5):
        """

        :param alpha: weighting coefficient
        """
        super(OutlierExposureLoss, self).__init__()
        self.alpha = alpha

    def forward(self, logits, target) -> torch.Tensor:
        """

        :param logits: class logits for predictions
        :param target: labels for predictions
        :return: loss
        """
        loss_ce = cross_entropy(logits, target)
        if contains_unknown(target):
            unknown = is_unknown(target)
            loss_oe = -(logits[unknown].mean(1) - torch.logsumexp(logits[unknown], dim=1)).mean()
        else:
            loss_oe = 0
        return loss_ce + self.alpha * loss_oe
