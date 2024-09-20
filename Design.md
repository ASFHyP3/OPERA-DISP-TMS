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
### Format
To fully understand the context of InSAR-derived displacement data (such as the OPERA-Disp products) multiple pieces are required for each pixel:

1. The geographic location of the pixel (from the GDAL metadata)
2. The start and end date for the displacement observation
3. The reference pixel location to which all displacement measurements in a product are relative to

This is a lot of information, and we will need to ensure that we provide access to all of this data (or at least make it trackable) for every pixel in the mosaic.

To do this, the 1x1 degree cumulative displacement COGs will have the following bands:
1. Float32 short wavelength cumulative displacement sourced directly from the products
2. UInt16 indicating cumulative displacement **secondary date** represented as days since 1/1/2014 (first calendar year of Sentinel-1 Mission)
3. UInt16 indicating the frame number the cumulative displacement value is sourced from

In addition to this per-COG information, there will also be one accompanying metadata rasters (in COG format) for each tile location (i.e., one per footprint). The metadata raster will have the same resolution, extent, and projection as the cumulative displacement COGs, and in fact will serve as the template for create cumulative displacement COGs. The metadata raster will have the following band:
1. UInt16 indicating the frame number the cumulative displacement value is sourced from

In addition, it will include the following metadata tags:
1. A list of the frames present in the frame band
2. The frame reference date in the format YYYY/MM/DD for each frame present in the tile
3. The frame reference point location encoded as the geographic coordinates of the reference pixel in the native projection of the frame for each frame present in the tile

For example, the fields in metadata raster may look like:
```
OPERA_FRAMES: "1, 2"
FRAME_1_REF_POINT: "129877.23, 128383.28"
FRAME_1_REF_DATE: "2015/01/01"
FRAME_2_REF_POINT: "22348.23, 38973.28"
FRAME_2_REF_DATE: "2015/02/01"
```
**Note: a time-series stack of OPERA-DISP products from the same frame are not guaranteed to have the same reference date or location!** However having 
the same spatiotemporal reference for each pixel in a time-series stack is an important requirement for date/location re-referencing and velocity calcultions. Thus, we standardize the spatiotemporal reference for each product before mosaicking. 

Note that we only standardize the spatiotemporal reference so that each location is consistent through time. We do not standardize this information across space. Non-continuous frame coverage, and varying data collection dates makes standardizing across space a difficult challenge that is planned to be undertaken during the creation of the OPERA-DISP Vertical Land Motion project.

### 1x1 Degree Tile Creation
Prior to mosaicking of OPERA-DISP products, we generate the metadata rasters.

For each 1x1 degree tile, there is one metadata raster for each orbit direction, for a total of two per tile. The metadata rasters will each span a 1x1 degree area in the web mercator (EPSG:3857) projection with a 30 m pixel spacing. The frame band is created by cross-referencing each tile's extent with the OPERA-DISP frame footprints. A geospatial representation of the OPERA-DISP frame footprints can be created using the [OPERA burst_db utility](https://github.com/opera-adt/burst_db). Frames will be overlaid so that frames from the same relative orbit are contiguous. Relative orbits are stacked from East to West on the ascending pass (West on top), and from West to East on the descending pass (East on top). Within a relative orbit, frames are overlaid so that older frames are on top of younger frames. This corresponds to North on top for the ascending pass, and South on top for the descending pass.

Once the frame band has been constructed, we set the spatiotemporal reference metadata using the values present in the earliest product available for each frame.

We then use the generated metadata rasters as a guide for creating all 1x1 degree cumulative displacement tiles in a time-series stack. The procedure is as follows:

- Specify a date range you want to generate a tile for
- Generate a new raster with the same projection, resolution, and extent as the metadata raster with three bands
    - Cumulative displacement
    - Days since 2014/01/01
    - Frame number
- Obtain the list of needed frames from the metadata raster metadata tags
- For each needed frame
    - Find OPERA-DISP product with the latest available secondary date within the date range
        - If a frame has no available product within the date range, raise an exception
    - Check that the product's spatiotemporal reference date is the same as the metadata raster
        - If this is not the case, re-reference the product (methodology will be written soon)
    - Reproject the product's cumulative displacement band to the same projection, resolution, and extent as the metadata raster
    - For the cells that correspond to the frame in question within the new raster
        - Set the cumulative displacement band values to the ones from the reprojected OPERA-DISP product
        - Set the Days since 2014/01/01 to the secondary date of the OPERA-DISP product
- Copy the frame number band from the metadata raster to the new raster
- Copy the spatiotemporal reference metadata from the metadata raster to the new raster

### MapBox Tileset Generation
TODO

