# Mosaic Design
## General Concept
There are two key steps for preparing OPERA DISP data for presentation in the MapBox Tiling Service:

1. The discrete, non-rectangular, and rotated frames of OPERA DISP products need to be summarized into a continuous single-layer raster representation.
2. This continuous representation needs to delivered to MapBox in a format that is simple for it to ingest.

To meet the first requirement, we take discrete OPERA DISP products and transform them into a set of square 1x1 degree COGs. This strategy has worked well for other projects (such as the Global Seasonal Coherence dataset) and allows us to easily convert the data to the tileset representation that MapBox. It also provides us with a great starting point to provide this data to users via other avenues (GIBS, ESRI Image Server, TMS, etc.) in the future. There are intricacies for mosaicking each product, which are detailed in other sections, but in general each tile is created separately using 1-4 input OPERA DISP products. Products are overlaid so that products along the same absolute orbit are continuous, and neighboring relative orbit data are overlaid from east to west. The 1x1 degree COGs maintain the same datatype and data values as the original products.

These 1x1 degree COGs are then summarized into a set of files that are ingestable into a [MapBox tileset source](https://docs.mapbox.com/mapbox-tiling-service/guides/tileset-sources/), the core unit of the MapBox Tiling Service. The requirements for this are as follows:
- UInt8 datatype
- Total dataset size of less than 50 GB
- No file greater than 10 GB
- No more than 10 input files per tileset source
A single tile map layer can be composed of multiple tileset sources if necessary to get around the 10 file limit, but testing has shown that we can meet the requirements above for a single tileset source that includes all of North America, which is sufficient for this project.

To go from the 1x1 degree COGs to a MapBox tileset source we must mosaic the 1x1 degree COGs into 10 or fewer tiled GeoTiffs with a UInt8 datatype. GeoTiffs are used because the overviews included in COGs are unused by MapBox, and only serve to increase file size. Dataset-specific discussions will need to had with the OPERA team concerning how to represent the datasets as UInt16 datatypes, but an initial guess of `round(pixel_value,2)*100) + 1` will be used for all datsets during initial development. Values above and below this range will be clipped to 255 and 0 respectively.

LZW or another compression method will be used for all files to reduce file sizes.

## Cumulative Displacement
To fully understand the context of InSAR-derived displacement data (such as the OPERA-Disp products) multiple pieces are required for each pixel:

1. The geographic location of the pixel (from the GDAL metadata)
2. The start and end date for the displacement observation
3. The reference pixel location to which all displacement measurements in a product are relative to

This is a lot of information, and we will need to ensure that we provide access to all of this data (or at least make it trackable) for every pixel in the mosaic.

To do this, the 1x1 degree cumulative displacement COGs will have the following bands:
1. Float32 short wavelength cumulative displacement sourced directly from the products
2. UInt16 indicating the frame number the cumulative displacement value is sourced from
3. UInt16 indicating cumulative displacement **reference date** represented as days since 1/1/2014 (beginning of Sentinel-1 Mission)
4. UInt16 indicating cumulative displacement **secondary date** represented as days since 1/1/2014 (beginning of Sentinel-1 Mission)
5. UInt32 indicating the pixel position of the reference pixel counting from left-to-right down the product array rows

Instead of including the reference pixel band, The combination of reference/secondary date and frame number is enough to identify which product a pixel observation came from, which could then accessed to identify the reference pixel location. However, this process is cumbersome and would slow down future velocity calculations, which require knowing the reference pixel location.

**For a given pixel location in a 1x1 degree COG, the same source frame must be used for all cumulative displacement products for that locations.** Otherwise, future differencing of cumulative displacement products to obtain alternate reference will provide incorrect data.


