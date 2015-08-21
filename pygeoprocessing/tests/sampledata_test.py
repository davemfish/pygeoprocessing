import unittest
import os

from osgeo import gdal
from osgeo import ogr
from osgeo import osr
import numpy
from shapely.geometry import Polygon

import pygeoprocessing
import pygeoprocessing.testing
from pygeoprocessing.testing import sampledata


class RasterTest(unittest.TestCase):
    def test_init(self):
        pixels = numpy.ones((4, 4), numpy.byte)
        nodata = 0
        reference = sampledata.SRS_COLOMBIA
        filename = pygeoprocessing.temporary_filename()

        sampledata.create_raster_on_disk(pixels, reference.origin,
                                         reference.projection,
                                         nodata, reference.pixel_size(30),
                                         datatype=gdal.GDT_Byte, format='GTiff',
                                         filename=filename)

        self.assertTrue(os.path.exists(filename))

        dataset = gdal.Open(filename)
        self.assertEqual(dataset.RasterXSize, 4)
        self.assertEqual(dataset.RasterYSize, 4)

        band = dataset.GetRasterBand(1)
        band_nodata = band.GetNoDataValue()
        self.assertEqual(band_nodata, nodata)

        dataset_sr = osr.SpatialReference()
        dataset_sr.ImportFromWkt(dataset.GetProjection())
        source_sr = osr.SpatialReference()
        source_sr.ImportFromWkt(reference.projection)
        self.assertTrue(dataset_sr.IsSame(source_sr))

    def test_bad_driver(self):
        reference = sampledata.SRS_COLOMBIA
        self.assertRaises(RuntimeError, sampledata.create_raster_on_disk,
                          numpy.ones((4, 4)),
                          reference.origin, reference.projection, 0,
                          reference.pixel_size(30), format='foo')

    def test_raster_autodtype(self):
        pixels = numpy.ones((4, 4), numpy.uint16)
        nodata = 0
        reference = sampledata.SRS_COLOMBIA
        filename = pygeoprocessing.temporary_filename()

        sampledata.create_raster_on_disk(pixels, reference.origin,
                                         reference.projection,
                                         nodata, reference.pixel_size(30),
                                         datatype='auto',
                                         filename=filename)

        dataset = gdal.Open(filename)
        band = dataset.GetRasterBand(1)
        band_dtype = band.DataType

        # numpy.uint16 should translate to gdal.GDT_UInt16
        self.assertEqual(band_dtype, gdal.GDT_UInt16)


class VectorTest(unittest.TestCase):
    def test_init(self):
        polygons = [
            Polygon([(0, 0), (1, 0), (0.5, 1), (0, 0)]),
        ]
        reference = sampledata.SRS_COLOMBIA

        filename = sampledata.create_vector_on_disk(polygons,
                                                    reference.projection)

        vector = ogr.Open(filename)
        layer = vector.GetLayer()

        features = layer.GetFeatureCount()
        self.assertEqual(features, 1)

    def test_mismatched_geoms_attrs(self):
        polygons = [
            Polygon([(0, 0), (1, 0), (0.5, 1), (0, 0)]),
        ]
        reference = sampledata.SRS_COLOMBIA
        fields = {'foo': 'int'}
        attrs = []
        self.assertRaises(AssertionError, sampledata.create_vector_on_disk,
                          polygons, reference.projection, fields, attrs)

    def test_wrong_field_type(self):
        polygons = []
        reference = sampledata.SRS_WILLAMETTE
        fields = {'foo': 'bar'}
        self.assertRaises(AssertionError, sampledata.create_vector_on_disk,
                          polygons, reference.projection, fields)

    def test_wrong_driver(self):
        self.assertRaises(AssertionError, sampledata.create_vector_on_disk, [],
                          sampledata.SRS_WILLAMETTE.projection,
                          vector_format='foobar')
