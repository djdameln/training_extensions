Object Detection
================

Object detection is a computer vision task where it's needed to locate objects, finding their bounding boxes coordinates together with defining class.
The input is an image, and the output is a pair of coordinates for bouding box corners and a class number for each detected object.

The common approach to building object detection architecture is to take a feature extractor (backbone), that can be inherited from the classification task.
Then goes a head that calculates coordinates and class probabilities based on aggregated information from the image.
Additionally, some architectures use `Feature Pyramid Network (FPN) <https://arxiv.org/abs/1612.03144>`_ to transfer and process feature maps from backbone to head and called neck.

For the supervised training we use the following algorithms components:

.. _od_supervised_pipeline:

- ``Augmentations``: We use random crop and random rotate, simple bright and color distortions and multiscale training for the training pipeline.

- ``Optimizer``: We use `SGD <https://en.wikipedia.org/wiki/Stochastic_gradient_descent>`_ optimizer with the weight decay set to **1e-4** and momentum set to **0.9**.

- ``Learning rate schedule``: `ReduceLROnPlateau <https://pytorch.org/docs/stable/generated/torch.optim.lr_scheduler.ReduceLROnPlateau.html>`_. This learning rate scheduler proved its efficiency in dataset-agnostic trainings, its logic is to drop LR after some time without improving the target accuracy metric. Also, we update it with ``iteration_patience`` parameter that ensures that a certain number of training iterations (steps through the dataset) were passed before dropping LR.

- ``Loss function``: We use `Generalized IoU Loss <https://giou.stanford.edu/>`_  for localization loss to train the ability of the model to find the coordinates of the objects. For the classification head, we use a standard `FocalLoss <https://arxiv.org/abs/1708.02002>`_.

- ``Additional training techniques``
    - ``Early stopping``: To add adaptability to the training pipeline and prevent overfitting. You can use early stopping like the below command.

      .. code-block::

        $ otx train {TEMPLATE} ... \
                    params \
                    --learning_parameters.enable_early_stopping=True

    - `Anchor clustering for SSD <https://arxiv.org/abs/2211.17170>`_: This model highly relies on predefined anchor boxes hyperparameter that impacts the size of objects, which can be detected. So before training, we collect object statistics within dataset, cluster them and modify anchor boxes sizes to fit the most for objects the model is going to detect.

    - ``Backbone pretraining``: we pretrained MobileNetV2 backbone on large `ImageNet21k <https://github.com/Alibaba-MIIL/ImageNet21K>`_ dataset to improve feature extractor and learn better and faster.


**************
Dataset Format
**************

At the current point we support `COCO <https://cocodataset.org/#format-data>`_ and
`Pascal-VOC <https://openvinotoolkit.github.io/datumaro/stable/docs/data-formats/formats/pascal_voc.html>`_ dataset formats.
Learn more about the formats by following the links above. Here is an example of expected format for COCO dataset:

.. code::

  ├── annotations/
      ├── instances_train.json
      ├── instances_val.json
      └── instances_test.json
  ├──images/
      (Split is optional)
      ├── train
      ├── val
      └── test

If you have your dataset in those formats, then you can simply run using one line of code:

.. code-block::

    $ otx train  <model_template> --train-data-roots <path_to_data_root> \
                                            --val-data-roots <path_to_data_root>

.. note::

    Please, refer to our :doc:`dedicated tutorial <../../../tutorials/base/how_to_train/detection>` for more information how to train, validate and optimize detection models.

******
Models
******

We support the following ready-to-use model templates:

+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| Template ID                                                                                                                                                                               | Name                | Complexity (GFLOPs) | Model size (MB) |
+===========================================================================================================================================================================================+=====================+=====================+=================+
| `Custom_Object_Detection_YOLOX <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/cspdarknet_yolox_tiny/template.yaml>`_ |      YOLOX-TINY     | 6.5                 | 20.4            |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_YOLOX_S <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/cspdarknet_yolox_s/template.yaml>`_         |       YOLOX_S       | 33.51               | 46.0            |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_YOLOX_L <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/cspdarknet_yolox_l/template.yaml>`_         |       YOLOX_L       | 194.57              | 207.0           |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_YOLOX_X <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/cspdarknet_yolox_x/template.yaml>`_         |       YOLOX_X       | 352.42              | 378.0           |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Custom_Object_Detection_Gen3_SSD <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/mobilenetv2_ssd/template.yaml>`_    |         SSD         | 9.4                 | 7.6             |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Custom_Object_Detection_Gen3_ATSS <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/mobilenetv2_atss/template.yaml>`_  |  MobileNetV2-ATSS   | 20.6                | 9.1             |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_ResNeXt101_ATSS <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnext101_atss/template.yaml>`_    |   ResNeXt101-ATSS   | 434.75              | 344.0           |
+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+

Above table can be found using the following command

.. code-block::
    $ otx find --task detection

`MobileNetV2-ATSS <https://arxiv.org/abs/1912.02424>`_ is a good medium-range model that works well and fast in most cases.
`SSD <https://arxiv.org/abs/1512.02325>`_ and `YOLOX <https://arxiv.org/abs/2107.08430>`_ are light models, that a perfect for the fastest inference on low-power hardware.
YOLOX achieved the same accuracy as SSD, and even outperforms its inference on CPU 1.5 times, but requires 3 times more time for training due to `Mosaic augmentation <https://arxiv.org/pdf/2004.10934.pdf>`_, which is even more than for ATSS.
So if you have resources for a long training, you can pick the YOLOX model.
ATSS still shows good performance among `RetinaNet <https://arxiv.org/abs/1708.02002>`_ based models. Therfore, We added ATSS with large scale backbone, ResNeXt101-ATSS. We integrated large ResNeXt101 backbone to our Custom ATSS head, and it shows good transfer learning performance.
In addition, we added a YOLOX variants to support users' diverse situations.

In addition to these models, we supports experimental models for object detection. These experimental models will be changed to official models within a few releases.

+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| Template ID                                                                                                                                                                                                               | Name                | Complexity (GFLOPs) | Model size (MB) |
+===========================================================================================================================================================================================================================+=====================+=====================+=================+
| `Object_Detection_Deformable_DETR <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnet50_deformable_detr/template_experimental.yaml>`_              |   Deformable_DETR   | 165                 | 157.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_DINO <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnet50_dino/template_experimental.yaml>`_                                    |        DINO         | 235                 | 182.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Object_Detection_Lite_DINO <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnet50_litedino/template_experimental.yaml>`_                           |      Lite-DINO      | 140                 | 190.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+


`Deformable_DETR <https://arxiv.org/abs/2010.04159>`_ is `DETR <https://arxiv.org/abs/2005.12872>`_ based model, and it solves slow convergence problem of DETR. `DINO <https://arxiv.org/abs/2203.03605>`_ improves Deformable DETR based methods via denoising anchor boxes. Current SOTA models for object detection are based on DINO.
`Lite-DINO <https://arxiv.org/abs/2303.07335>`_ is efficient structure for DINO. It reduces FLOPS of transformer's encoder which takes the highest computational costs.

.. note::

    For using experimental templates, you should specify full path of experimental template. Ex) otx build src/otx/algorithms/detection/configs/detection/resnet50_dino/template_experimental.yaml --task detection

In addition to these models, we supports experimental models for object detection. These experimental models will be changed to official models within a few releases.

+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| Template ID                                                                                                                                                                                                               | Name                | Complexity (GFLOPs) | Model size (MB) |
+===========================================================================================================================================================================================================================+=====================+=====================+=================+
| `Custom_Object_Detection_Gen3_Deformable_DETR <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnet50_deformable_detr/template_experimental.yaml>`_  |   Deformable_DETR   | 165                 | 157.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Custom_Object_Detection_Gen3_DINO <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnet50_dino/template_experimental.yaml>`_                        |        DINO         | 235                 | 182.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+
| `Custom_Object_Detection_Gen3_ResNeXt101_ATSS <https://github.com/openvinotoolkit/training_extensions/blob/develop/src/otx/algorithms/detection/configs/detection/resnext101_atss/template_experimental.yaml>`_           |   ResNeXt101-ATSS   | 434.75              | 344.0           |
+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+---------------------+---------------------+-----------------+

`Deformable_DETR <https://arxiv.org/abs/2010.04159>`_ is `DETR <https://arxiv.org/abs/2005.12872>`_ based model, and it solves slow convergence problem of DETR. `DINO <https://arxiv.org/abs/2203.03605>`_ improves Deformable DETR based methods via denoising anchor boxes. Current SOTA models for object detection are based on DINO.
Although transformer based models show notable performance on various object detection benchmark, CNN based model still show good performance with proper latency.
Therefore, we added a new experimental CNN based method, ResNeXt101-ATSS. ATSS still shows good performance among `RetinaNet <https://arxiv.org/abs/1708.02002>`_ based models. We integrated large ResNeXt101 backbone to our Custom ATSS head, and it shows good transfer learning performance.

.. note::

    For using experimental templates, you should specify full path of experimental template. Ex) otx build src/otx/algorithms/detection/configs/detection/resnet50_dino/template_experimental.yaml --task detection

Besides this, we support public backbones from `torchvision <https://pytorch.org/vision/stable/index.html>`_, `pytorchcv <https://github.com/osmr/imgclsmob>`_, `mmcls <https://github.com/open-mmlab/mmclassification>`_ and `OpenVino Model Zoo <https://github.com/openvinotoolkit/open_model_zoo>`_.
Please, refer to the :doc:`tutorial <../../../tutorials/advanced/backbones>` how to customize models and run public backbones.

To see which public backbones are available for the task, the following command can be executed:

.. code-block::
    $ otx find --backbone {torchvision, pytorchcv, mmcls, omz.mmcls}

In the table below the test mAP on some academic datasets using our :ref:`supervised pipeline <od_supervised_pipeline>` is presented.

For `COCO <https://cocodataset.org/#home>`__ dataset the accuracy of pretrained weights is shown, and we report official COCO mAP with AP50.
Except for COCO, we report AP50 as performance metric.

5 datasets were selected as transfer learning datasets.
`BDD100K <https://www.bdd100k.com/>`_ is the largest dataset among we used. 70000 images are used as train images and 10000 images are used for validation.
`Brackish <https://public.roboflow.com/object-detection/brackish-underwater>`_ and `Plantdoc <https://public.roboflow.com/object-detection/plantdoc>`_ are datasets of medium size. They have around 10000 images for train and 1500 images for validation.
`BCCD <https://public.roboflow.com/object-detection/bccd>`_ and `Chess pieces <https://public.roboflow.com/object-detection/chess-full>`_ are datasets of small size. They have around 300 images for train and 100 images for validation.
We used our own templates without any modification.
For hyperparameters, please, refer to the related template.
We trained each model with a single Nvidia GeForce RTX3090.

+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| Model name                 | COCO(AP50)       | BDD100K   | Brackish  | Plantdoc  | BCCD      | Chess pieces |
+============================+==================+===========+===========+===========+===========+==============+
| YOLOX-TINY                 | 31.0 (48.2)      | 24.8      | 96.3      | 51.5      | 88.5      | 99.2         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| SSD                        | 13.5             | 28.2      | 96.5      | 52.9      | 91.1      | 99.1         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| MobileNetV2-ATSS           | 32.5 (49.5)      | 40.2      | 99.1      | 63.4      | 93.4      | 99.1         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| ResNeXt101-ATSS            | 45.1 (63.8)      | 45.5      | 99.3      | 69.3      | 93.1      | 99.1         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| ResNet50-Deformable-DETR   | 44.3 (63.2)      | 44.8      | 97.7      | 60.7      | 93.4      | 99.2         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| ResNet50-DINO              | 49.0 (66.4)      | 47.2      | 99.5      | 62.9      | 93.5      | 99.1         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| ResNet50-Lite-DINO         | 48.1 (64.4)      | 47.0      | 99.0      | 62.5      | 93.6      | 99.4         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| YOLOX-S                    | 40.3 (59.1)      | 37.1      | 93.6      | 54.8      | 92.7      | 98.8         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| YOLOX-L                    | 49.4 (67.1)      | 44.5      | 94.6      | 55.8      | 91.8      | 99.0         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+
| YOLOX-X                    | 50.9 (68.4)      | 44.2      | 96.3      | 56.2      | 91.5      | 98.9         |
+----------------------------+------------------+-----------+-----------+-----------+-----------+--------------+

************************
Semi-supervised Learning
************************

For Semi-SL task solving we use the `Unbiased Teacher model <https://arxiv.org/abs/2102.09480>`_, which is a specific implementation of Semi-SL for object detection. The unbiased teacher detaches the student model and the teacher model to prevent the teacher from being polluted by noisy pseudo-labels. In the early stage, the teacher model is trained by supervised loss. This stage is called a burn-in stage. After the burn-in, the student model is trained using both pseudo-labeled data from the teacher model and labeled data. And the teacher model is updated using
EMA.

In Semi-SL, the pseudo-labeling process is combined with a consistency loss that ensures that the predictions of the model are consistent across augmented versions of the same data. This helps to reduce the impact of noisy or incorrect labels that may arise from the pseudo-labeling process. Additionally, our algorithm uses a combination of strong data augmentations and a specific optimizer called Sharpness-Aware Minimization (SAM) to further improve the accuracy of the model.

Overall, OpenVINO™ Training Extensions utilizes powerful techniques for improving the performance of Semi-SL algorithm with limited labeled data. They can be particularly useful in domains where labeled data is expensive or difficult to obtain, and can help to reduce the time and cost associated with collecting labeled data.

.. _od_semi_supervised_pipeline:

- ``Pseudo-labeling``: A specific implementation of Semi-SL that combines the use of pseudo-labeling with a consistency loss, strong data augmentations, and a specific optimizer called Sharpness-Aware Minimization (SAM) to improve the performance of the model.

- ``Weak & Strong augmentation``: For teacher model weak augmentations(random flip) are applied to input image. For the student model strong augmentations(colorjtter, grayscale, goussian blur, random erasing) are applied.

- ``Additional training techniques``: Other than that, we use several solutions that apply to supervised learning (No bias Decay, Augmentations, Early stopping, LR conditioning.).

Please, refer to the :doc:`tutorial <../../../tutorials/advanced/semi_sl>` how to train semi supervised learning.

In the table below the mAP on toy data sample from `COCO <https://cocodataset.org/#home>`__ dataset using our pipeline is presented.

We sample 400 images that contain one of [person, car, bus] for labeled train images. And 4000 images for unlabeled images. For validation 100 images are selected from val2017.

+---------------------+--------------------------------------------+
| Dataset             |            Sampled COCO dataset            |
+=====================+=====================+======================+
|                     |          SL         |       Semi-SL        |
+---------------------+---------------------+----------------------+
|  MobileNetV2-ATSS   |  | Person: 69.70    | | Person: 69.44      |
|                     |  | Car:    65.00    | | Car:    65.84      |
|                     |  | Bus:    42.96    | | Bus:    50.7       |
|                     |  | Mean:   59.20    | | Mean:   61.98      |
+---------------------+---------------------+----------------------+
|   SSD               | | Person: 39.24     | | Person: 38.52      |
|                     | | Car:    19.24     | | Car:    28.02      |
|                     | | Bus:    21.34     | | Bus:    26.28      |
|                     | | Mean:   26.60     | | Mean:   30.96      |
+---------------------+---------------------+----------------------+
|  YOLOX              | | Person: 65.64     | | Person: 69.00      |
|                     | | Car:    64.44     | | Car:   65.66       |
|                     | | Bus:    60.68     | | Bus:   65.12       |
|                     | | Mean:   63.6      | | Mean:  66.58       |
+---------------------+---------------------+----------------------+

.. ************************
.. Self-supervised Learning
.. ************************

.. To be added soon

.. ********************
.. Incremental Learning
.. ********************

.. To be added soon
