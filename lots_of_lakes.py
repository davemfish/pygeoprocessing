import collections
import logging
import os
import contextlib
import time
import cProfile
import StringIO
import pstats
import glob

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

import shapely
import shapely.wkb
import shapely.geometry
from osgeo import gdal
import numpy

import pygeoprocessing
import pygeoprocessing.testing
import pygeoprocessing.routing
import taskgraph


@contextlib.contextmanager
def time_it(message):
    LOGGER.info(message)
    start_time = time.time()
    yield
    LOGGER.info('Finished %s in %ss', message.lower(), time.time() - start_time)


@contextlib.contextmanager
def profile(filename=None):
    profiler = cProfile.Profile()
    profiler.enable()
    yield
    profiler.disable()

    if not filename:
        stream = StringIO.StringIO()
    else:
        stream = open(filename, 'w')

    ps = pstats.Stats(profiler, stream=stream).sort_stats('cumulative')
    ps.print_stats()

    if not filename:
        print stream.getvalue()
    else:
        stream.close()

WILLAMETTE_ROADS = (
    'workspace-willamette-roads',
    os.path.normpath(r'../../natcap/invest/data/invest-data/Base_Data/Terrestrial/roads.shp'),
    #r'roadsegment.shp',
    #r'roadsegments.shp',
    os.path.normpath(r'../../natcap/invest/data/invest-data/Base_Data/Freshwater/dem/hdr.adf'))


STACIES_SUBSET = (
    'workspace-stacie-subset',
    r'C:\Users\jdouglass\Downloads\waterbodies_DEM_Montana_sample\waterbodies_DEM_Montana_sample\waterbodies_NHD_3fc.shp',
    r'C:\Users\jdouglass\Downloads\waterbodies_DEM_Montana_sample\waterbodies_DEM_Montana_sample\dem_reprojected.tif')

ALL_OF_MONTANA = (
    'workspace-montana',
    r'C:\Users\jdouglass\workspace\jdouglass\snippets\in-development-watershed-delination-sample\NDD_Montana_waterbodies1.gpkg',
    r'C:\Users\jdouglass\workspace\jdouglass\snippets\in-development-watershed-delination-sample\merged_montana.tif')


def compare_scratch_to_fragments(vector, rasterized_path, raster2):
    pygeoprocessing.new_raster_from_base(
        raster2, rasterized_path, gdal.GDT_UInt32, [2**32-1], fill_value_list=[0])

    pygeoprocessing.rasterize(
        vector_path=vector,
        target_raster_path=rasterized_path,
        option_list=['ATTRIBUTE=fragment_id'])

    pygeoprocessing.testing.assert_rasters_equal(rasterized_path, raster2)


def _load_geometries(vector_path, layer_name=None):
    if not layer_name:
        layer_name = 0

    geometries = {}
    vector = gdal.OpenEx(vector_path)
    layer = vector.GetLayer(layer_name)
    for feature in layer:
        ogr_geom = feature.GetGeometryRef()
        shapely_geom = shapely.wkb.loads(ogr_geom.ExportToWkb())
        geometries[tuple(sorted(feature.items().keys()))] = (feature.GetFID(), shapely_geom)

    return geometries


def compare_trivial_to_joined(trivial_watersheds_path, joined_fragments_path):
    # Shapely polygons are immutable, so instead I'll index them by area and
    # then compare the geometries.
    trivial_geometries = _load_geometries(trivial_watersheds_path)
    joined_geometries = _load_geometries(joined_fragments_path)

    n_missing = 0
    n_geoms_not_matched = 0

    trivial_filename = os.path.basename(trivial_watersheds_path)
    joined_filename = os.path.basename(joined_fragments_path)

    for keys, (fid, geom) in trivial_geometries.items():
        if keys not in joined_geometries:
            print "%s FID %s not found in %s" % (
                trivial_filename, fid, joined_filename)
            n_missing += 1
            continue

        joined_fid, joined_geom = joined_geometries[bounds]
        if not (joined_geom.difference(geom).area == 0 and
                geom.difference(joined_geom).area == 0 and
                geom.union(joined_geom).area == geom.area and
                joined_geom.union(geom).area == geom.area):
            print "%s FID %s geom does not match %s FID %s" % (
                trivial_filename, fid, joined_fid, joined_filename)
            n_geoms_not_matched += 1
            continue

    print 'n_missing', n_missing
    print 'n geoms not matched', n_geoms_not_matched


def find_fragments_split_between_features(vector_path):
    vector = gdal.OpenEx(vector_path)
    layer = vector.GetLayer()
    features = collections.defaultdict(set)
    for feature in layer:
        features[feature.GetField('fragment_id')].add(feature.GetFID())

    return [fragment_id for (fragment_id, fids) in features.items() if len(fids)]


def subtract_counts(matrix_a, matrix_b):
    # assume nodata of 0
    output = numpy.zeros_like(matrix_a)
    valid_pixels = (matrix_a == 0) | (matrix_b == 0)
    output[valid_pixels] = numpy.absolute(
        matrix_a[valid_pixels] - matrix_b[valid_pixels], dtype=numpy.uint8)
    return output


def doit():
    handler = logging.FileHandler('latest-logfile.txt', 'w', encoding='UTF-8')
    formatter = logging.Formatter(
            '%(asctime)s %(name)-18s %(levelname)-8s %(message)s',
            '%m/%d/%Y %H:%M:%S ')
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.NOTSET)
    handler.setFormatter(formatter)
    handler.setLevel(logging.NOTSET)

    # Willamette roads, from the sample data
    workspace, lakes, dem = WILLAMETTE_ROADS

    # Stacie's subset of lakes from NHD.
    #workspace, lakes, dem = STACIES_SUBSET

    # Biggest Montana dataset I have at the moment.
    #workspace, lakes, dem = ALL_OF_MONTANA

    #workspace = 'D:\\new-watershed-delineation'
    if not os.path.exists(workspace):
        os.makedirs(workspace)

    filled_dem = os.path.join(workspace, 'filled_dem.tif')
    flow_dir = os.path.join(workspace, 'flow_dir_d8.tif')
    fragments_path = os.path.join(workspace, 'fragments.gpkg')
    joined_fragments = os.path.join(workspace, 'joined_fragments.gpkg')
    trivial_watersheds = os.path.join(workspace, 'watersheds_trivial.gpkg')
    trivial_burned = os.path.join(workspace, 'watersheds_trivial_count.tif')
    joined_burned = os.path.join(workspace, 'joined_fragments_count.tif')
    count_mismatch = os.path.join(workspace, 'fragment_count_mismatch.tif')

    task_graph = taskgraph.TaskGraph(
        os.path.join(workspace, 'tg_workers'), n_workers=2,
        reporting_interval=10.0)

    filled_pits_task = task_graph.add_task(
        pygeoprocessing.routing.fill_pits,
        args=((dem, 1), filled_dem),
        target_path_list=[filled_dem])

    d8_flow_dir_task = task_graph.add_task(
        pygeoprocessing.routing.flow_dir_d8,
        args=((filled_dem, 1), flow_dir, workspace),
        target_path_list=[flow_dir],
        dependent_task_list=[filled_pits_task])

    new_delineation_task = task_graph.add_task(
        pygeoprocessing.routing.delineate_watersheds_d8,
        args=((flow_dir, 1), lakes, fragments_path, workspace),
        target_path_list=[fragments_path],
        dependent_task_list=[d8_flow_dir_task])

    joining_task = task_graph.add_task(
        pygeoprocessing.routing.join_watershed_fragments_stack,
        args=(fragments_path, joined_fragments),
        target_path_list=[joined_fragments],
        dependent_task_list=[new_delineation_task])


    trivial_delineation_task = task_graph.add_task(
        pygeoprocessing.routing.delineate_watersheds_trivial_d8,
        args=((flow_dir, 1), lakes, trivial_watersheds),
        kwargs={'working_dir': workspace},
        target_path_list=[trivial_watersheds],
        dependent_task_list=[d8_flow_dir_task])

    task_graph.close()
    task_graph.join()

    pygeoprocessing.new_raster_from_base(
        filled_dem, trivial_burned, gdal.GDT_UInt32, [0], fill_value_list=[0])
    pygeoprocessing.rasterize(
        trivial_watersheds, trivial_burned, burn_values=[1],
        option_list=['MERGE_ALG=ADD'])

    pygeoprocessing.new_raster_from_base(
        filled_dem, joined_burned, gdal.GDT_UInt32, [0], fill_value_list=[0])
    pygeoprocessing.rasterize(
        joined_fragments, joined_burned, burn_values=[1],
        option_list=['MERGE_ALG=ADD'])

    pygeoprocessing.raster_calculator(
        [(trivial_burned, 1), (joined_burned, 1)],
        subtract_counts, count_mismatch, gdal.GDT_Byte, 0)

    n_pixels_mismatched = 0
    for block_data, block in pygeoprocessing.iterblocks((count_mismatch, 1)):
        n_pixels_mismatched += numpy.count_nonzero(block)

    print 'MISMATCH', n_pixels_mismatched


    compare_trivial_to_joined(
        trivial_watersheds, joined_fragments)
    compare_trivial_to_joined(
        joined_fragments, trivial_watersheds)

    handler.close()
    root_logger.removeHandler(handler)

if __name__ == '__main__':
    doit()
