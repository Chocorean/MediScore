python2 /mnt/Backend1/Server/MediScore/tools/DetectionScorer/DetectionScorer.py --sysDir /Users/tnk12/Documents/MediScoreV2/tools/DetectionScorer/DSWrapper/system/ --refDir /Users/tnk12/Documents/MediScoreV2/tools/DetectionScorer/DSWrapper/ -s /Users/tnk12/Documents/MediScoreV2/tools/DetectionScorer/DSWrapper/system/kitware-holistic-image-v18_20190327-120000.csv --outMeta --outSubMeta --dump --outRoot /Users/tnk12/Documents/MediScoreV2/tools/DetectionScorer/DSWrapper/output --farStop 0.05 --ciLevel 0.90 --ci -qm "Operation==['TransformCrop', 'TransformCropResize'] or PlugInName==['CropByPercentage','FaceCrop']" -t manipulation -x indexes/MFC19_EvalPart1-manipulation-image-index.csv -r reference/manipulation-image/MFC19_EvalPart1-manipulation-image-ref.csv --plotTitle kitware-holistic-image-v18_20190327-120000