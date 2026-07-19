#!/bin/bash

# Inputs
#    - Input KMZ
#    - Output tiff filename

kmz=$1
output=$2

# Validate KMZ
if [ -z "${kmz}" ];
then
	echo "Error: no input file specified"
	exit 1
fi

echo "Processing file $kmz"

# Unzip to tmp directory
rm -rf tmp/
mkdir tmp
unzip -o $kmz -d tmp/

# Extract coordinates from kml
north=$(grep -oPm1 "(?<=<north>)[^<]+" tmp/doc.kml)
south=$(grep -oPm1 "(?<=<south>)[^<]+" tmp/doc.kml)
east=$(grep -oPm1 "(?<=<east>)[^<]+" tmp/doc.kml)
west=$(grep -oPm1 "(?<=<west>)[^<]+" tmp/doc.kml)

# Get image filename from kml
inFile=$(grep -oPm1 "(?<=<href>files/)[^<]+" tmp/doc.kml)

# Get output filename from input filename
outFile="${inFile%.*}.tiff"

# Get file path
outPath=$(dirname "$kmz")

echo "Image boundaries: [${north},${west}] (top left), [${south},${east}] (bottom right)"
echo "Processing image ${inFile} and saving to ${outFile}"

# Convert to GeoTiff (expand palette to RGB)
gdal_translate -a_srs EPSG:4326 -a_ullr $west $north $east $south -expand rgb tmp/files/$inFile $outFile

# Convert RGB colors to dBm values
dbm_tiff="dbm_${outFile}"
python3 rgb_to_dbm.py $outFile $dbm_tiff

# Remove tmp files
rm -r tmp/

# Move geotiff to original location
mv $outFile $outPath
mv $dbm_tiff $outPath

