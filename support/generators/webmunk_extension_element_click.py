# pylint: disable=line-too-long

import csv
import datetime
import gc
import io
import os
import tempfile

import pytz

from django.conf import settings

from passive_data_kit.models import DataPoint, DataSource, DataGeneratorDefinition, DataSourceReference

from ..pdk_api import remove_newlines

def extract_secondary_identifier(properties):
    if 'element-class' in properties:
        return properties['element-class']

    return None

def generator_name(identifier): # pylint: disable=unused-argument
    return 'Webmunk: Page Click'

def compile_report(generator, sources, data_start=None, data_end=None, date_type='created'): # pylint: disable=too-many-locals, too-many-statements
    filename = tempfile.gettempdir() + os.path.sep + generator + '.txt'

    with io.open(filename, 'w', encoding='utf-8') as outfile:
        writer = csv.writer(outfile, delimiter='\t')

        columns = [
            'Source',
            'Date Created',
            'Date Recorded',
            'Time Zone',
            'Tab ID',
            'Element Class',
            'Top',
            'Left',
            'Width',
            'Height',
            'URL',
            'Page Title',
            'Element HTML',
        ]

        writer.writerow(columns)

        click_reference = DataGeneratorDefinition.definition_for_identifier('webmunk-extension-element-click')

        for source in sorted(sources): # pylint: disable=too-many-nested-blocks
            # print('Source: %s' % (source))

            gc.collect()

            data_source = DataSource.objects.filter(identifier=source).first()

            if data_source is not None and data_source.server is None:
                gc.collect()

                source_ref = DataSourceReference.reference_for_source(source)

                if data_end is not None and data_start is not None:
                    if (data_end - data_start).days < 1:
                        data_start = data_end - datetime.timedelta(days=1)

                date_sort = '-created'

                points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=click_reference)

                if date_type == 'created':
                    if data_start is not None:
                        points = points.filter(created__gte=data_start)

                    if data_end is not None:
                        points = points.filter(created__lte=data_end)

                if date_type == 'recorded':
                    if data_start is not None:
                        points = points.filter(recorded__gte=data_start)

                    if data_end is not None:
                        points = points.filter(recorded__lte=data_end)

                    date_sort = '-recorded'

                points = points.order_by(date_sort)

                points_count = points.count()

                points_index = 0

                while points_index < points_count:
                    # print('  Index: %d / %d' % (points_index, points_count))

                    for point in points[points_index:(points_index + 100)]:
                        properties = point.fetch_properties()

                        row = []

                        row.append(point.source)

                        tz_str = properties['passive-data-metadata'].get('timezone', settings.TIME_ZONE)

                        here_tz = pytz.timezone(tz_str)

                        created = point.created.astimezone(here_tz)
                        recorded = point.recorded.astimezone(here_tz)

                        row.append(created.isoformat())
                        row.append(recorded.isoformat())

                        row.append(tz_str)

                        here_tz = pytz.timezone(tz_str)

                        row.append(properties.get('tab-id', ''))

                        row.append(properties.get('element-class', ''))

                        offset = properties.get('offset', {})

                        row.append(offset.get('top', ''))
                        row.append(offset.get('left', ''))

                        size = properties.get('size', {})

                        row.append(size.get('width', ''))
                        row.append(size.get('height', ''))

                        row.append(properties.get('url*', ''))
                        row.append(properties.get('page-title*', properties.get('page-title!', '')))
                        row.append(remove_newlines(properties.get('element-content*', properties.get('element-content!', ''))))

                        writer.writerow(row)

                    points_index += 100

    return filename
