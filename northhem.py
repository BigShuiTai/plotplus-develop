import functools
import os, pickle
import numpy as np
from plotplus import gpf
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as ciosr
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
from cartopy.util import add_cyclic_point

__version__ = '0.1.1'

_ShapeFileDir = os.path.join(os.path.split(__file__)[0], 'shapefile')
_ProvinceDir = os.path.join(_ShapeFileDir, 'CP/ChinaProvince.shp')
_CityDir = os.path.join(_ShapeFileDir, 'CHN/CHN_adm2.shp')
_CityTWDir = os.path.join(_ShapeFileDir, 'TWN/TWN_adm2.shp')
_CountyDir = os.path.join(_ShapeFileDir, 'CHN/CHN_adm3.shp')

class Northhem:

    def __init__(self, figsize=(6,6), dpi=140, central_longitude=0, extent=[-180,180,0,90]):
        self.mmnote = ''
        self.dpi = dpi
        self.fig = plt.figure(figsize=figsize)
        self.ax = self.fig.add_axes([0, 0, 1, 1], projection=ccrs.NorthPolarStereo(central_longitude=central_longitude))
        self.crs = ccrs.PlateCarree()
        self.ax.set_extent(extent, crs=self.crs)
        self.family = 'DejaVu Sans'
        self.fontsize = dict(title=7.5, timestamp=6.5, mmnote=6.5, clabel=5, cbar=5,
                             gridvalue=5, mmfilter=6, parameri=4, legend=6,
                             marktext=5)
        self.linecolor = dict(coastline='#222222', lakes='#222222', rivers='#222222', country='#222222', province='#222222',
            city='#222222', county='#222222', parameri='k')
        self.linewidth = dict(coastline=0.3, lakes=0.2, rivers=0.2, country=0.3, province=0.3, city=0.1,
            county=0.1, parameri=0.3)
    
    def setfamily(self, f):
        self.family = f

    def setfontsize(self, name, size):
        self.fontsize.update({name:size})

    def setlinecolor(self, name, size):
        self.linecolor.update({name:size})

    def setdpi(self, dpi):
        self.dpi = dpi
    
    def usefeature(self, feature, facecolor=None, edgecolor=None, **kwargs):
        feature._kwargs.update(facecolor=facecolor, edgecolor=edgecolor)
        self.ax.add_feature(feature, **kwargs)

    def useshapefile(self, directory, encoding='utf8', color=None, lw=None, **kwargs):
        if lw is None:
            lw = self.linewidth['province']
        kwargs.update(linewidth=lw)
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(directory).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), **kwargs)

    def drawcoastline(self, scale='10m', lw_coast=None, lw_river=None, lw_lake=None, color_coast=None, color_river=None, color_lake=None, facecolor='none', res=None, rivers=False, lakes=True):
        lw_coast = self.linewidth['coastline'] if lw_coast is None else lw_coast
        lw_river = self.linewidth['rivers'] if lw_river is None else lw_river
        lw_lake = self.linewidth['lakes'] if lw_lake is None else lw_lake
        color_coast = self.linecolor['coastline'] if color_coast is None else color_coast
        color_river = self.linecolor['rivers'] if color_river is None else color_river
        color_lake = self.linecolor['lakes'] if color_lake is None else color_lake
        self.ax.add_feature(cfeature.COASTLINE.with_scale(scale),
            facecolor=facecolor, edgecolor=color_coast, linewidth=lw_coast)
        if rivers:
            self.ax.add_feature(cfeature.RIVERS.with_scale(scale),
                facecolor=facecolor, edgecolor=color_river, linewidth=lw_river)
        if lakes:
            self.ax.add_feature(cfeature.LAKES.with_scale(scale),
                facecolor=facecolor, edgecolor=color_lake, linewidth=lw_lake)
    
    def drawcoastline(self, scale='10m', lw=0.3, facecolor='none', edgecolor='k'):
        self.ax.add_feature(cfeature.COASTLINE.with_scale(scale), facecolor=facecolor, edgecolor=edgecolor, lw=lw)
    
    def drawprovince(self, lw=0.3, facecolor='none', edgecolor='k'):
        lw = self.linewidth['province'] if lw is None else lw
        edgecolor = self.linecolor['province'] if edgecolor is None else edgecolor
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_ProvinceDir).geometries(),
            ccrs.PlateCarree(), facecolor=facecolor, edgecolor=edgecolor), linewidth=lw)
    
    def drawcity(self, lw=0.3, facecolor='none', edgecolor='k'):
        lw = self.linewidth['city'] if lw is None else lw
        edgecolor = self.linecolor['city'] if edgecolor is None else edgecolor
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CityDir).geometries(),
            ccrs.PlateCarree(), facecolor=facecolor, edgecolor=edgecolor), linewidth=lw)
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CityTWDir).geometries(),
            ccrs.PlateCarree(), facecolor=facecolor, edgecolor=edgecolor), linewidth=lw)
    
    def drawcounty(self, lw=0.3, facecolor='none', edgecolor='k'):
        lw = self.linewidth['county'] if lw is None else lw
        edgecolor = self.linecolor['county'] if edgecolor is None else edgecolor
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CountyDir).geometries(),
            ccrs.PlateCarree(), facecolor=facecolor, edgecolor=edgecolor), linewidth=lw)
    
    def stepcal(self, lonmax, lonmin, num, res, ip=1):
        totalpt = (lonmax - lonmin) / res * ip
        return int(totalpt / num)
    
    def legend(self, lw=0., **kwargs):
        rc = dict(loc='upper right', framealpha=0.)
        rc.update(kwargs)
        ret = self.ax.legend(prop=dict(size=self.fontsize['legend'], family=self.family),
                             **rc)
        ret.get_frame().set_linewidth(lw)
        return ret

    def plot(self, *args, **kwargs):
        ret = self.ax.plot(*args, **kwargs)
        return ret

    def scatter(self, *args, **kwargs):
        ret = self.ax.scatter(*args, **kwargs)
        return ret

    def contour(self, x, y, data, clabel=True, clabeldict=dict(), color='k', lw=0.5, vline=None, vlinedict=dict(), **kwargs):
        data, x = add_cyclic_point(data, coord=x[0,:])
        x, y = np.meshgrid(x, y[:,0])
        kwargs.update(colors=color, linewidths=lw)
        c = self.ax.contour(x, y, data, transform=self.crs, **kwargs)
        if vline:
            vlinedict = merge_dict(vlinedict, {'color':color, 'lw':lw})
            if isinstance(vline, (int, float)):
                vline = [vline]
            for v in vline:
                if not isinstance(v, (int, float)):
                    raise ValueError('`{}` should be int or float'.format(v))
                try:
                    index = list(c.levels).index(v)
                except ValueError:
                    raise ValueError('{} not in contour levels'.format(v))
                else:
                    c.collections[index].set(**vlinedict)
        if clabel:
            if 'levels' in clabeldict:
                clabellevels = clabeldict.pop('levels')
            else:
                clabellevels = kwargs['levels']
            merge_dict(clabeldict, {'fmt': '%d', 'fontsize': self.fontsize['clabel']})
            labels = self.ax.clabel(c, **clabeldict)
            for l in labels:
                l.set_family(self.family)
                if vline:
                    text = l.get_text()
                    for v in vline:
                        if str(v) == text:
                            l.set_color(vlinedict['color'])
        return c

    def contourf(self, x, y, data, gpfcmap=None, **kwargs):
        if gpfcmap:
            kwargs = merge_dict(kwargs, gpf.cmap(gpfcmap))
        data, x = add_cyclic_point(data, coord=x[0,:])
        x, y = np.meshgrid(x, y[:,0])
        c = self.ax.contourf(x, y, data, transform=self.crs, **kwargs)
        return c
    
    def pcolormesh(self, x, y, data, gpfcmap=None, **kwargs):
        if gpfcmap:
            import matplotlib.colors as mclr
            gpfdict = gpf.cmap(gpfcmap)
            cmap = gpfdict.pop('cmap')
            levels = gpfdict.pop('levels')
            norm = mclr.BoundaryNorm(levels, ncolors=cmap.N, clip=True)
            kwargs.update(cmap=cmap, norm=norm)
        data, x = add_cyclic_point(data, coord=x[0,:])
        x, y = np.meshgrid(x, y[:,0])
        ret = self.ax.pcolormesh(x, y, data, transform=self.crs, **kwargs)
        return ret
    
    def streamplot(self, u, v, color='w', lw=0.3, density=2, **kwargs):
        kwargs.update(color=color, linewidth=lw, density=density)
        ret = self.ax.streamplot(self.x, self.y, u, v, **kwargs)
        return ret
    
    def colorbar(self, mappable, unit=None, **kwargs):
        if kwargs.pop('sidebar', False):
            return self.sidebar(mappable, unit, **kwargs)
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        kwargs = merge_dict(kwargs, dict(size='2%', pad='1%'))
        if kwargs.pop('orientation', None) == 'horizontal':
            location = 'bottom'
            orientation = 'horizontal'
        else:
            location = 'right'
            orientation = 'vertical'
            self._colorbar_unit(unit)
        divider = make_axes_locatable(self.ax)
        aspect = self.ax.get_aspect()
        if isinstance(aspect, (int, float)):
            # `axes_grid1` would fail when source axe has aspect set. The colorbar
            # would remain at the same place as aspect isn't set. So we use `pad`
            # param to explicitly re-position the colorbar. Yes, it looks hacky.
            pad_num = int(kwargs['pad'].strip('%')) / 100
            pad_num = pad_num - (1 - 1 / aspect) / 2
            kwargs['pad'] = '{:.02%}'.format(pad_num)
        cax = divider.append_axes(location, size=kwargs.pop('size'),
            pad=kwargs.pop('pad'), axes_class=plt.Axes)
        cb = self.fig.colorbar(mappable, orientation=orientation, cax=cax, **kwargs)
        self.fig.sca(self.ax)
        cb.ax.tick_params(labelsize=self.fontsize['cbar'], length=0, pad=2)
        cb.outline.set_linewidth(0.3)
        for l in cb.ax.yaxis.get_ticklabels():
            l.set_family(self.family)
        return cb
    
    def sidebar(self, mappable, unit=None, **kwargs):
        ticks = kwargs.pop('ticks')
        ticks = [ticks[0], ticks[-1]]
        cax = self.fig.add_axes([0.18, 0.13, 0.01, 0.05])
        cb = self.fig.colorbar(mappable, cax=cax, ticks=ticks, **kwargs)
        cb.ax.tick_params(labelsize=self.fontsize['cbar'], length=0)
        cb.outline.set_linewidth(0.1)
        for l in cb.ax.yaxis.get_ticklabels():
            l.set_family(self.family)
        plt.sca(self.ax)
        return cb
    
    def title(self, s):
        self.ax.text(0, 1.03, s, transform=self.ax.transAxes, fontsize=self.fontsize['title'],
                     family=self.family)
    
    def timestamp(self, basetime, fcsthour, duration=0, nearest=None):
        stdfmt = '%Y/%m/%d %a %HZ'
        if isinstance(basetime, str):
            basetime = datetime.strptime(basetime, '%Y%m%d%H')
        if duration:
            if duration > 0:
                fcsthour = fcsthour, fcsthour + duration
            else:
                fcsthour = fcsthour + duration, fcsthour
        elif nearest:
            validtime = basetime + timedelta(hours=fcsthour - 1)
            nearesttime = validtime.replace(hour=validtime.hour // nearest * nearest)
            fcsthour = fcsthour + nearesttime.hour - validtime.hour - 1, fcsthour
        if isinstance(fcsthour, int):
            validtime = basetime + timedelta(hours=fcsthour)
            s = '%s [+%dh] valid at %s' % (basetime.strftime(stdfmt), fcsthour,
                                              validtime.strftime(stdfmt))
        elif isinstance(fcsthour, str):
            if fcsthour == 'an':
                s = basetime.strftime(stdfmt)
            else:
                s = ''
        else:
            fcsthour = tuple(fcsthour)
            fromhour, tohour = fcsthour
            fromtime = basetime + timedelta(hours=fromhour)
            totime = basetime + timedelta(hours=tohour)
            s = '%s [+%d~%dh] valid from %s to %s' % (basetime.strftime(stdfmt),
                                                      fromhour, tohour, fromtime.strftime(stdfmt),
                                                      totime.strftime(stdfmt))
        self._timestamp(s)

    def _timestamp(self, s):
        self.ax.text(0, 1.01, s, transform=self.ax.transAxes,
                     fontsize=self.fontsize['timestamp'], family=self.family)

    def _colorbar_unit(self, s):
        if s:
            self.ax.text(1.05, 1.01, s, transform=self.ax.transAxes, ha='right',
                         fontsize=self.fontsize['timestamp'], family=self.family)

    def maxminnote(self, data, name, unit, type='max', fmt='%.1f'):
        type = type.lower()
        if type == 'max':
            typestr = 'Max.'
            notevalue = np.amax(data)
        elif type == 'min':
            typestr = 'Min.'
            notevalue = np.amin(data)
        elif type == 'mean':
            typestr = 'Mean'
            notevalue = np.mean(data)
        else:
            raise PlotError('Unsupported type!')
        notestr = '%s %s: ' % (typestr, name) + fmt % notevalue + ' ' + unit
        if self.mmnote != '':
            self.mmnote = self.mmnote + ' | ' + notestr
        else:
            self.mmnote = notestr

    def _maxminnote(self, s):
        self.mmnote = s
    
    def _colorbar_unit(self, s):
        if s:
            self.ax.text(1.05, 1.01, s, transform=self.ax.transAxes, ha='right',
                         fontsize=self.fontsize['timestamp'], family=self.family)
    
    def stdsave(self, directory, basetime, fcsthour, imcode):
        if isinstance(basetime, str):
            basetime = datetime.strptime(basetime, '%Y%m%d%H')
        path = os.path.join(directory, '%s_%s_%d_%d%d%d%d.png' % \
                            (basetime.strftime('%Y%m%d%H'), imcode, fcsthour, self.latmin,
                             self.latmax, self.lonmin, self.lonmax))
        self.save(path)

    def save(self, path, axis=True):
        self.ax.text(1, 1.01, self.mmnote, ha='right', transform=self.ax.transAxes,
                     fontsize=self.fontsize['mmnote'], family=self.family)
        if not axis:
            self.ax.axis('off')
        self.fig.savefig(path, dpi=self.dpi, bbox_inches='tight', edgecolor='none',
                         pad_inches=0.05)
    
    def close(self, para='all'):
        plt.close(para)

def merge_dict(a, b):
    '''Merge B into A without overwriting A'''
    for k, v in b.items():
        if k not in a:
            a[k] = v
    return a