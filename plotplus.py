import gc
import functools
import os
import pickle
import warnings
from datetime import datetime, timedelta

import plotplus.gpf as gpf

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib import font_manager

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as ciosr

import numpy as np
import scipy.ndimage as snd

__version__ = '0.5.0-dev'

_ShapeFileDir = os.path.join(os.path.split(__file__)[0], 'shapefile')
_CountryDir = os.path.join(_ShapeFileDir, '国家/国家.shp')

# _CN_ProvinceDir = os.path.join(_ShapeFileDir, 'CP/ChinaProvince.shp')
_CN_ProvinceDir = os.path.join(_ShapeFileDir, '南海诸岛/nanhai.shp')
_CN_CityDir = os.path.join(_ShapeFileDir, 'CHN/CHN_adm2.shp')
_CN_CityTWDir = os.path.join(_ShapeFileDir, 'TWN/TWN_adm2.shp')
_CN_CountyDir = os.path.join(_ShapeFileDir, 'CHN/CHN_adm3.shp')

_US_ProvinceDir = os.path.join(_ShapeFileDir, 'USA/gadm41_USA_1.shp')
_US_CityDir = os.path.join(_ShapeFileDir, 'USA/gadm41_USA_2.shp')

_black = '#222222'
_gray = '#444444'
_projshort = dict(P='PlateCarree', L='LambertConformal', ML='Miller', M='Mercator',
    N='NorthPolarStereo', S='SouthPolarStereo', G='Geostationary')
_scaleshort = dict(l='110m', i='50m', h='10m')


class PlotError(Exception):

    pass


class Plot:

    def __init__(self, figsize=None, dpi=180, aspect=None, inside_axis=False,
            boundary=None):
        """Init the plot.
        Parameters
        ---------------
        figsize : tuple, optional
            Tuple of (width, height) in inches. (the default is
            (7, 5).)
        dpi : int, optional
            DPI for figure. (the default is 180.)
        aspect : string or float, optional
            Aspect ratio for lat/lon, only work in PlateCarree
            projection. If set, height of figure will be calculated
            by (lat_range / lon_range) * width_of_figure * aspect.
            This param is often used when representing data in mid-
            latitude regions in PlateCarree projection to offset
            projection distortion.
            If set to 'auto', aspect will be calculated to fit the
            figure size.
            If set to None, aspect would be fixed to 1, figure size
            will be re-calculated to reflect the aspect ratio of
            georange.
            If set to 'cos', aspect would be fixed to
            1 / cos(avg(latmin, latmax)) and figure size will be
            re-calculated accordingly. This option is to
            automatically reduce distortion in mid-latitude regions.
            (the default is None.)
        inside_axis : boolean, optional
            Whether all figure artists are placed inside the bounding
            box. If True, title/colorbar method is ignored, gridline
            labels are placed inside. Padding will be set to zero.
            (the default is False.)
        boundary : string, optional
            Should be one of (None|round|rect). If None, no boundary
            will be drew. If set as `round`, a round boundary will be
            plotted, which is often used in polar-centric projections.
            If set as `rect`, a rectangle boundary will be drew. (the
            default is None)
        """
        self.mmnote = ''
        self.family = 'Lato'
        self.dpi = dpi
        if figsize is None:
            figsize = 7, 5
        self.fig = plt.figure(figsize=figsize)
        self.ax = None
        self.facecolor = None
        self.mpstep = 10
        self.mapset = None
        self.aspect = aspect
        self.boundary = boundary
        self.inside_axis = inside_axis
        self.no_parameri = False
        self.fontsize = dict(title=6.5, timestamp=5, mmnote=5, clabel=5, cbar=5,
            gridvalue=5, mmfilter=6, parameri=4, legend=6, marktext=6,
            boxtext=6, footer=6)
        self.linecolor = dict(coastline=_black, lakes=_black, rivers=_black, country=_black, province=_black,
            city=_gray, county=_gray, parameri='k')
        self.linewidth = dict(coastline=0.3, lakes=0.2, rivers=0.2, country=0.3, province=0.3, city=0.1,
            county=0.1, parameri=0.3)

    def setfamily(self, f):
        self.family = f

    def setfont(self, font_file, size):
        fontProperties = font_manager.FontProperties(fname=font_file, size=size)
        return fontProperties

    def setfontsize(self, name, size):
        self.fontsize[name] = size

    def setfacecolor(self, color):
        self.facecolor = color

    def setlinecolor(self, name, color):
        self.linecolor[name] = color

    def setlinewidth(self, name, width):
        self.linewidth[name] = width

    def setmeriparastep(self, mpstep):
        self.mpstep = mpstep

    def setparameristep(self, mpstep):
        self.mpstep = mpstep

    def setdpi(self, d):
        self.dpi = d

    def setxy(self, lons, lats, georange, res):
        self.res = res
        self.xx, self.yy = lons, lats
        self.x, self.y = self.xx[0, :], self.yy[:, 0]
        self.latmin, self.latmax, self.lonmin, self.lonmax = tuple(georange)
        self._latmin, self._latmax, self._lonmin, self._lonmax = (
            np.nanmin(self.y), np.nanmax(self.y),
            np.nanmin(self.x), np.nanmax(self.x)
        )
        self.uneven_xy = False

    def _setxy(self, x, y):
        self.xx = x
        self.yy = y
        self.uneven_xy = True

    def setmap(self, key=None, proj='ML', projection=None, resolution='i',
            **kwargs):
        """Set underlying map for the plot.
        Parameters
        ----------
        key : string, optional
            Shortcut key for built-in maps. Available options:
            chinaproper|chinamerc|chinalambert|euroasia|europe|
            northamerica|northpole (the default is None)
        proj : string, instance of ccrs, optional
            Cartopy-style projection names or shortcut names or
            cartopy crs instance. Available shortcut options:
            P - PlateCarree|L - LambertConformal|M - Mercator|
            N - NorthPolarStereo|G - Geostationary
        projection : string, optional
            Basemap-style projection names. Only following options
            are allowed: cyl|merc|lcc|geos|npaepd (the default is
            None)
        resolution : string, optional
            Default scale of features (e.g. coastlines). Should be
            one of (l|i|h), which stands for 110m, 50m and 10m
            respectively. The default is 'i' (50m).
        """
        if 'resolution' in kwargs:
            kwargs.pop('resolution')
            warnings.warn('Param `resolution` is ignored in plotplus2.')
        if key is not None:
            proj, other_kwargs = self._from_map_key(key)
            kwargs.update(other_kwargs)
        if proj is None and projection is not None:
            _proj_dict = {'cyl':'P', 'merc':'M', 'lcc':'L', 'geos':'G', 'npaeqd':'N', 'spaeqd':'S'}
            proj = _proj_dict.get(projection, None)
            if proj is None:
                raise PlotError('Only cyl/merc/lcc/geos/npaeqd are allowed in `projection` '
                                'param. If you want to use cartopy-style projection names, '
                                'please use `proj` param instead.')
        self.georange = kwargs.pop('georange') if 'georange' in kwargs else (-90, 90, -180, 180)
        self.map_georange = kwargs.pop('map_georange') if 'map_georange' in kwargs else self.georange
        if 'facecolor' in kwargs:
            self.facecolor = kwargs.pop('facecolor')
        if isinstance(proj, ccrs.Projection):
            _proj = proj
            self.proj = type(_proj).__name__
        else:
            self.proj = _projshort.get(proj.upper(), proj)
            if not 'central_longitude' in kwargs:
                central_longitude = (self.georange[2] + self.georange[3]) / 2
                kwargs.update(central_longitude=central_longitude)
            _proj = getattr(ccrs, self.proj)(**kwargs)
        self.trans = self.proj != 'PlateCarree'
        self.ax = plt.axes(projection=_proj)
        if self.facecolor is not None:
            self.ax.patch.set_facecolor(self.facecolor)
        self.scale = _scaleshort[resolution]
        extent = self.map_georange[2:] + self.map_georange[:2]
        self.ax.set_extent(extent, crs=ccrs.PlateCarree())
        width, height = self.fig.get_size_inches()
        deltalon = self.map_georange[3] - self.map_georange[2]
        deltalat = self.map_georange[1] - self.map_georange[0]
        if self.aspect == 'auto':
            aspect_ratio = (height * deltalon) / (width * deltalat)
            self.ax.set_aspect(aspect_ratio)
        elif self.aspect == 'cos':
            midlat = (self.map_georange[0] + self.map_georange[1]) / 2
            aspect_ratio = 1 / np.cos(np.deg2rad(midlat))
            self.fig.set_size_inches(width, width * deltalat / deltalon * aspect_ratio)
            self.ax.set_aspect(aspect_ratio)
        elif self.aspect is not None:
            self.ax.set_aspect(self.aspect)
        else:
            # self.fig.set_size_inches(width, width * deltalat / deltalon)
            pass
        if self.boundary is None:
            self.ax.patch.set_linewidth(0)
        elif self.boundary == 'rect':
            self.ax.patch.set_linewidth(0.5)
        elif self.boundary == 'round':
            # For north polar stereo projection
            import matplotlib.path as mpath
            theta = np.linspace(0, 2*np.pi, 100)
            center, radius = [0.5, 0.5], 0.5
            verts = np.vstack([np.sin(theta), np.cos(theta)]).T
            circle = mpath.Path(verts * radius + center)
            self.ax.set_boundary(circle, transform=self.ax.transAxes, linewidth=0.5)
        else:
            raise PlotError('Unknown boundary type.')

    def _from_map_key(self, key):
        self.no_parameri = True
        if key == 'chinaproper':
            proj = 'P'
            kwargs = {'georange':(20,40,100,130)}
        elif key == 'chinamerc':
            proj = 'M'
            kwargs = {'georange':(15,50,72.5,135)}
        elif key == 'chinalambert':
            proj = 'L'
            kwargs = {'georange':(15,55,80,125), 'central_longitude':102.5,
                'central_latitude':40, 'standard_parallels':(40,40)}
        elif key == 'euroasia':
            proj = 'L'
            kwargs = {'georange':(5,75,55,145), 'central_longitude':100,
                'central_latitude':40, 'standard_parallels':(40,40)}
        elif key == 'europe':
            proj = 'ML'
            kwargs = {'georange':(30,70,-25,45), 'central_longitude':0}
        elif key == 'northpac':
            proj = 'L'
            kwargs = {'georange':(-5,70,120,250), 'central_longitude':185,
                'central_latitude':42.5, 'standard_parallels':(0,40)}
        elif key == 'northamerica':
            proj = 'L'
            kwargs = {'georange':(5,75,-145,-55), 'central_longitude':-100,
                'central_latitude':40, 'standard_parallels':(40,40)}
        elif key == 'northpolar':
            proj = 'N'
            kwargs = {'georange':(15,90,-180,180), 'central_longitude':105}
        elif key == 'southpolar':
            proj = 'S'
            kwargs = {'georange':(-90,-15,-180,180), 'central_longitude':105}
        else:
            self.no_parameri = False
        return proj, kwargs

    def usemap(self, session):
        proj = session.mapproj.pop('proj')
        georange = session.mapproj.pop('georange')
        self.setmap(proj=proj, georange=georange, **session.mapproj)

    def usefeature(self, feature, facecolor=None, edgecolor=None, **kwargs):
        feature._kwargs.update(facecolor=facecolor, edgecolor=edgecolor)
        self.ax.add_feature(feature, **kwargs)

    def usemapset(self, mapset, proj=None):
        self.mapset = mapset
        projection = proj or mapset.proj
        if self.ax is None and projection:
            if mapset.proj_params:
                proj_params = mapset.proj_params
            else:
                proj_params = {}
            self.setmap(proj=projection, georange=mapset.georange, **proj_params)

    def useshapefile(self, directory, encoding='utf8', color=None, lw=None, **kwargs):
        if lw is None:
            lw = self.linewidth['province']
        kwargs.update(linewidth=lw)
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(directory).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), **kwargs)

    def drawcoastline(self, lw_coast=None, lw_river=None, lw_lake=None, color_coast=None, color_river=None, color_lake=None, res=None, rivers=False, lakes=True):
        lw_coast = self.linewidth['coastline'] if lw_coast is None else lw_coast
        lw_river = self.linewidth['rivers'] if lw_river is None else lw_river
        lw_lake = self.linewidth['lakes'] if lw_lake is None else lw_lake
        color_coast = self.linecolor['coastline'] if color_coast is None else color_coast
        color_river = self.linecolor['rivers'] if color_river is None else color_river
        color_lake = self.linecolor['lakes'] if color_lake is None else color_lake
        res = res if res else self.scale
        if self.mapset and self.mapset.coastline:
            self.usefeature(self.mapset.coastline, edgecolor=color_coast, facecolor='none',
                linewidth=lw_coast)
            if self.mapset.lakes or lakes:
                self.usefeature(self.mapset.lakes, edgecolor=color_lake, facecolor='none',
                    linewidth=lw_lake)
            if self.mapset.rivers or rivers:
                self.usefeature(self.mapset.rivers, edgecolor=color_river, facecolor='none',
                    linewidth=lw_river)
        else:
            self.ax.add_feature(self.getfeature('physical', 'coastline', res,
                facecolor='none', edgecolor=color_coast), linewidth=lw_coast)
            if rivers:
                self.ax.add_feature(cfeature.RIVERS.with_scale(res),
                facecolor='none', edgecolor=color_river, linewidth=lw_river)
            if lakes:
                self.ax.add_feature(cfeature.LAKES.with_scale(res),
                facecolor='none', edgecolor=color_lake, linewidth=lw_lake)

    def drawcountry(self, lw=None, color=None, res=None):
        lw = self.linewidth['country'] if lw is None else lw
        color = self.linecolor['country'] if color is None else color
        res = res if res else self.scale
        if self.mapset and self.mapset.country:
            self.usefeature(self.mapset.country, edgecolor=color, facecolor='none',
                linewidth=lw)
        else:
            self.ax.add_feature(cfeature.ShapelyFeature(
                ciosr.Reader(_CountryDir).geometries(), ccrs.PlateCarree(),
                facecolor='none', edgecolor=color), linewidth=lw)

    @functools.lru_cache(maxsize=32)
    def getfeature(self, *args, **kwargs):
        return cfeature.NaturalEarthFeature(*args, **kwargs)

    def drawprovince(self, lw=None, color=None):
        lw = self.linewidth['province'] if lw is None else lw
        color = self.linecolor['province'] if color is None else color
        if self.mapset and self.mapset.province:
            self.usefeature(self.mapset.province, edgecolor=color, facecolor='none',
                linewidth=lw)
        else:
            self.ax.add_feature(cfeature.ShapelyFeature(
                ciosr.Reader(_CN_ProvinceDir).geometries(), ccrs.PlateCarree(),
                facecolor='none', edgecolor=color), linewidth=lw)
            self.ax.add_feature(cfeature.ShapelyFeature(
                ciosr.Reader(_US_ProvinceDir).geometries(), ccrs.PlateCarree(),
                facecolor='none', edgecolor=color), linewidth=lw)
        if self.stepcal(num=20) < 4:
            self.drawcity()
        if self.stepcal(num=20) == 1:
            self.drawcounty()

    def drawcity(self, lw=None, color=None):
        lw = self.linewidth['city'] if lw is None else lw
        color = self.linecolor['city'] if color is None else color
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CN_CityDir).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), linewidth=lw)
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CN_CityTWDir).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), linewidth=lw)
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_US_CityDir).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), linewidth=lw)

    def drawcounty(self, lw=None, color=None):
        lw = self.linewidth['county'] if lw is None else lw
        color = self.linecolor['county'] if color is None else color
        self.ax.add_feature(cfeature.ShapelyFeature(ciosr.Reader(_CN_CountyDir).geometries(),
            ccrs.PlateCarree(), facecolor='none', edgecolor=color), linewidth=lw)

    def drawparameri(self, lw=None, color=None, fontsize=None, **kwargs):
        if self.no_parameri:
            return
        import cartopy.mpl.gridliner as cmgl
        import matplotlib.ticker as mticker
        no_dashes = lw is None and (self.proj == 'PlateCarree' or \
            self.proj == 'Mercator' or self.proj == 'Miller')
        lw = self.linewidth['parameri'] if lw is None else lw
        color = self.linecolor['parameri'] if color is None else color
        fontsize = self.fontsize['parameri'] if fontsize is None else fontsize
        kwargs = merge_dict(kwargs, {'dashes': (0, (7, 7))})
        gl = self.ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=lw,
            color=color, linestyle='--', **kwargs)
        gl.top_labels = False
        gl.right_labels = False
        gl.xlocator = mticker.FixedLocator(np.arange(-180, 181, self.mpstep))
        gl.ylocator = mticker.FixedLocator(np.arange(-80, 81, self.mpstep))
        gl.xformatter = cmgl.LONGITUDE_FORMATTER
        gl.yformatter = cmgl.LATITUDE_FORMATTER
        gl.xlabel_style = dict(size=fontsize, color=color, family=self.family)
        gl.ylabel_style = dict(size=fontsize, color=color, family=self.family)
        gl.x_inline = False
        gl.y_inline = False
        gl.rotate_labels = False
        if no_dashes:
            gl.xlines = False
            gl.ylines = False
        if self.inside_axis:
            gl.xpadding = -8
            gl.ypadding = -12
        else:
            gl.xpadding = 3
            gl.ypadding = 2
        # set extent note manually
        lon_ticks = np.arange(-180, 181, self.mpstep)
        lat_ticks = np.arange(-90, 91, self.mpstep)
        if 180 <= self.lonmin < self.lonmax or self.lonmin <= 180 <= self.lonmax:
            lon_ticks[lon_ticks < 0] += 360
        xlabels = lon_ticks[(lon_ticks>=self.lonmin) & (lon_ticks<=self.lonmax)]
        ylabels = lat_ticks[(lat_ticks>=self.latmin) & (lat_ticks<=self.latmax)]
        if len(xlabels) == 0 or len(ylabels) == 0:
            yloc = -0.02 if len(xlabels) == 0 else -0.06
            self.ax.text(1, yloc, f"Area Extent: {self.georange}", va='top', ha='right', color='red', transform=self.ax.transAxes,
                        fontsize=self.fontsize['footer'], family=self.family)

    def draw(self, cmd):
        cmd = cmd.lower()
        if ' ' in cmd:
            for c in cmd.split():
                self.draw(c)
        else:
            if cmd == 'coastline' or cmd == 'coastlines':
                self.drawcoastline()
            elif cmd == 'country' or cmd == 'countries':
                self.drawcountry()
            elif cmd == 'province' or cmd == 'provinces':
                self.drawprovince()
            elif cmd == 'city' or cmd == 'cities':
                self.drawcity()
            elif cmd == 'county' or cmd == 'counties':
                self.drawcounty()
            elif cmd == 'parameri' or cmd == 'meripara':
                self.drawparameri()
            else:
                print('Illegal draw command: %s' % (cmd))

    def smooth_data(self, data, sigma=5, order=0):
        smoothed_data = snd.gaussian_filter(data, sigma=sigma, order=order)
        return smoothed_data

    def interpolation(self, data, ip=1):
        if self.uneven_xy:
            if ip > 1:
                print('Uneven x/y are not prepared for interpolation.')
            return self.xx, self.yy, data
        elif ip <= 1:
            return self.xx, self.yy, data
        else:
            nx = np.arange(self._lonmin, self._lonmax+self.res/ip, self.res/ip)
            ny = np.arange(self._latmin, self._latmax+self.res/ip, self.res/ip)
            newx, newy = np.meshgrid(nx, ny)
            xcoords = (len(self.x)-1)*(newx-self.x[0])/(self.x[-1]-self.x[0])
            ycoords = (len(self.y)-1)*(newy-self.y[0])/(self.y[-1]-self.y[0])
            coords = [ycoords, xcoords]
            ndata = snd.map_coordinates(data, coords, order=3, mode='nearest')
            return newx, newy, ndata

    def transform_data(self, data, ip=1):
        xx, yy, data = self.interpolation(data, ip=ip)
        ret = self.ax.projection.transform_points(ccrs.PlateCarree(),
            xx, yy, data)
        xx = ret[..., 0]
        yy = ret[..., 1]
        data = ret[..., 2]
        return xx, yy, data

    def stepcal(self, num, ip=1):
        if self.uneven_xy:
            # Meaningless for uneven x/y.
            return 1
        totalpt = (self._lonmax - self._lonmin) / self.res * ip
        return int(totalpt / num) if totalpt >= num else 1

    def legend(self, lw=0., **kwargs):
        rc = dict(loc='upper right', framealpha=0.)
        rc.update(kwargs)
        ret = self.ax.legend(prop=dict(family=self.family, size=self.fontsize['legend']),
                             **rc)
        ret.get_frame().set_linewidth(lw)
        return ret

    def style(self, s):
        if s not in ('jma', 'bom', 'fnmoc', 'blackBGRadar'):
            print('Unknown style name. Only support jma, bom, fnmoc, and blackBGRadar style.')
            return
        if s == 'jma':
            ocean_color = '#87A9D2'
            land_color = '#AAAAAA'
            self.linecolor.update(coastline='#666666', lakes='#666666', rivers='#666666', country='#666666',
                parameri='#666666', province='#888888', city='#888888')
            self.style_colors = (ocean_color, land_color, '#666666', '#888888')
        elif s == 'bom':
            ocean_color = '#E6E6FF'
            land_color = '#E8E1C4'
            self.linecolor.update(coastline='#D0A85E', lakes='#D0A85E', rivers='#D0A85E', country='#D0A85E',
                parameri='#D0A85E', province='#D0A85E', city='#D0A85E')
            self.style_colors = (ocean_color, land_color, '#D0A85E')
        elif s == 'fnmoc':
            ocean_color = '#CBCBCB'
            land_color = '#A0522E'
            self.linecolor.update(coastline='k', lakes='k', rivers='k', country='k',
                parameri='k', province='k', city='k')
            self.style_colors = (ocean_color, land_color, 'k')
        elif s == 'blackBGRadar':
            ocean_color = '#000000'
            land_color = '#000000'
            self.linecolor.update(coastline='w', lakes='k', rivers='w', country='w',
                parameri='w', province='w', city='w')
            self.style_colors = (ocean_color, land_color, 'w')
        if self.mapset and self.mapset.ocean:
            self.ax.add_feature(self.mapset.ocean, color=ocean_color)
        else:
            self.ax.add_feature(cfeature.OCEAN.with_scale(self.scale),
                color=ocean_color)
        if self.mapset and self.mapset.land:
            self.ax.add_feature(self.mapset.land, color=land_color)
        else:
            self.ax.add_feature(cfeature.LAND.with_scale(self.scale),
                color=land_color)
        if self.mapset and self.mapset.lakes:
            self.ax.add_feature(self.mapset.lakes, color=ocean_color)
        else:
            self.ax.add_feature(cfeature.LAKES.with_scale(self.scale),
                color=ocean_color)
        """
        if self.mapset and self.mapset.rivers:
            self.ax.add_feature(self.mapset.rivers, color=ocean_color)
        else:
            self.ax.add_feature(cfeature.RIVERS.with_scale(self.scale),
                color=ocean_color)
        """

    def plot(self, *args, **kwargs):
        kwargs.update(transform=ccrs.PlateCarree())
        ret = self.ax.plot(*args, **kwargs)
        return ret

    def scatter(self, *args, **kwargs):
        kwargs.update(transform=ccrs.PlateCarree())
        ret = self.ax.scatter(*args, **kwargs)
        return ret

    def imshow(self, im, gpfcmap=None, extent=None, **kwargs):
        kwargs.update(transform=ccrs.PlateCarree(), interpolation='nearest')
        if extent is None:
            kwargs.update(extent=self.map_georange[2:]+self.map_georange[:2])
        if gpfcmap:
            cmapdict = gpf.cmap(gpfcmap)
            levels = cmapdict['levels']
            vmin = levels.min()
            vmax = levels.max()
            kwargs.update(cmap=cmapdict['cmap'], vmin=vmin, vmax=vmax)
        ret = self.ax.imshow(im, **kwargs)
        return ret

    def text(self, *args, **kwargs):
        return self.ax.text(*args, **kwargs)

    def reltext(self, *args, **kwargs):
        kwargs.update(transform=self.ax.transAxes)
        return self.ax.text(*args, **kwargs)

    def _text(self, *args, **kwargs):
        kwargs.update(transform=ccrs.PlateCarree())
        return self.ax.text(*args, **kwargs)

    def annotate(self, *args, **kwargs):
        return self.ax.annotate(*args, **kwargs)

    def contour(self, data, clabel=True, clabeldict=None, ip=1, color='k', lw=0.5,
            vline=None, vlinedict=None, **kwargs):
        clabeldict = clabeldict or {}
        vlinedict = vlinedict or {}
        xx, yy, data = self.transform_data(data, ip)
        kwargs.update(colors=color, linewidths=lw, transform=self.ax.projection)
        c = self.ax.contour(xx, yy, data, **kwargs)
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
                    pass
                else:
                    c.collections[index].set(**vlinedict)
        if clabel:
            if 'levels' in clabeldict:
                clabellevels = clabeldict.pop('levels')
            else:
                clabellevels = kwargs['levels']
            merge_dict(clabeldict, {'fmt': '%d', 'fontsize': self.fontsize['clabel']})
            labels = self.ax.clabel(c, **clabeldict)
            if not labels:
                return c
            zorder = clabeldict.pop('zorder', 2)
            for l in labels:
                l.set_family(self.family)
                l.set_zorder(zorder)
                if not vline:
                    continue
                text = l.get_text()
                for v in vline:
                    if str(v) == text:
                        l.set_color(vlinedict['color'])
        return c

    def contourf(self, data, gpfcmap=None, cbar=False, cbardict=None, ip=1,
            vline=None, vlinedict=None, **kwargs):
        cbardict = cbardict or {}
        vlinedict = vlinedict or {}
        if gpfcmap:
            kwargs = merge_dict(kwargs, gpf.cmap(gpfcmap))
        unit = kwargs.pop('unit', None)
        xx, yy, data = self.transform_data(data, ip)
        kwargs.update(transform=self.ax.projection)
        c = self.ax.contourf(xx, yy, data, **kwargs)
        if cbar:
            if 'ticks' not in cbardict:
                levels = kwargs['levels']
                step = len(levels) // 40 + 1
                cbardict.update(ticks=levels[::step])
            if 'extend' in kwargs:
                cbardict.update(extend=kwargs.pop('extend'), extendfrac=0.02)
            self.colorbar(c, unit=unit, **cbardict)
        if vline is not None:
            if 'color' not in vlinedict:
                vlinedict.update(colors='w')
            if 'lw' not in vlinedict:
                vlinedict.update(linewidths=0.6)
            else:
                vlinedict.update(linewidths=vlinedict.pop('lw'))
            vlinedict.update(transform=self.ax.projection)
            self.ax.contour(xx, yy, data, levels=[vline], **vlinedict)
        return c

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

    def custom_colorbar(self, cmap=None, gpfcmap=None, location=None,
                        orientation='vertical', ticks=None, unit=None, label=None):
        from matplotlib.colorbar import ColorbarBase
        from matplotlib.colors import BoundaryNorm
        if location is None:
            location = [1.01, 0.0, 0.02, 1.0]
        if gpfcmap is not None:
            cmap_dict = gpf.cmap(gpfcmap)
            cmap = cmap_dict['cmap']
            levels = cmap_dict['levels']
            extend = cmap_dict['extend']
            if ticks is None:
                level_step = len(levels) // 40 + 1
                ticks = levels[::level_step]
            norm = BoundaryNorm(levels, ncolors=cmap.N, clip=True)
        else:
            extend = None
            norm = None
        cax = self.ax.inset_axes(location)
        cb = ColorbarBase(cax, cmap=cmap, orientation=orientation, ticks=ticks,
                          extendfrac=0.02, extend=extend, norm=norm)
        cb.ax.tick_params(labelsize=self.fontsize['cbar'], length=0, pad=1.2)
        cb.outline.set_linewidth(0.3)
        if label:
            cb.set_label(label, fontsize=self.fontsize['cbar'], family=self.family)
        for l in cb.ax.yaxis.get_ticklabels():
            l.set_family(self.family)
        self._colorbar_unit(unit)
        return cb

    def streamplot(self, u, v, color='w', lw=0.3, density=1, **kwargs):
        kwargs.update(color=color, linewidth=lw, density=density, transform=ccrs.PlateCarree())
        ret = self.ax.streamplot(self.xx, self.yy, u, v, **kwargs)
        return ret

    def barbs(self, u, v, color='k', lw=0.5, length=3.5, num=12, **kwargs):
        kwargs.update(color=color, linewidth=lw, length=length,
            transform=ccrs.PlateCarree(), regrid_shape=num)
        if self.yy[self.yy<=0].size > self.yy[self.yy>=0].size:
            nh = self.yy > 0
            sh = self.yy <= 0
        else:
            nh = self.yy >= 0
            sh = self.yy < 0
        if np.any(nh):
            ret = self.ax.barbs(self.xx[nh], self.yy[nh], u[nh], v[nh], **kwargs)
        else:
            ret = None
        if np.any(sh):
            retsh = self.ax.barbs(self.xx[sh], self.yy[sh], u[sh], v[sh],
                flip_barb=True, **kwargs)
        else:
            retsh = None
        return ret, retsh

    def quiver(self, u, v, c=None, num=40, scale=500, qkey=False, qkeydict=None, width=0.0015, **kwargs):
        qkeydict = qkeydict or {}
        kwargs.update(width=width, headwidth=3, scale=scale, transform=ccrs.PlateCarree(), regrid_shape=num)
        if c is not None:
            q = self.ax.quiver(self.xx, self.yy, u, v, c, **kwargs)
        else:
            q = self.ax.quiver(self.xx, self.yy, u, v, **kwargs)
        if qkey:
            if 'x' in qkeydict and 'y' in qkeydict:
                x = qkeydict.pop('x')
                y = qkeydict.pop('y')
            else:
                x, y = 0.5, 1.01
            unit = 'm/s' if 'unit' not in qkeydict else qkeydict.pop('unit')
            self.ax.quiverkey(q, x, y, scale, '%d%s' % (scale, unit), labelpos='W',
                              fontproperties=dict(family=self.family, size=8))
        return q

    def pcolormesh(self, data, gpfcmap=None, cbar=False, cbardict=None, ip=1, **kwargs):
        cbardict = cbardict or {}
        if gpfcmap:
            import matplotlib.colors as mclr
            gpfdict = gpf.cmap(gpfcmap)
            cmap = gpfdict.pop('cmap')
            levels = gpfdict.pop('levels')
            norm = mclr.BoundaryNorm(levels, ncolors=cmap.N, clip=True)
            kwargs.update(cmap=cmap, norm=norm)
        xx, yy, data = self.interpolation(data, ip)
        ret = self.ax.pcolormesh(xx, yy, data, transform=ccrs.PlateCarree(), **kwargs)
        if cbar:
            if 'ticks' not in cbardict:
                step = len(levels) // 40 + 1
                cbardict.update(ticks=levels[::step])
            cbardict.update(size='2%', pad='1%')
            if 'extend' in gpfdict:
                cbardict.update(extend=gpfdict.pop('extend'), extendfrac=0.02)
            self.colorbar(ret, unit=gpfdict.pop('unit', None), **cbardict)
        return ret

    def _get_stroke_patheffects(self):
        import matplotlib.patheffects as mpatheffects
        return [mpatheffects.Stroke(linewidth=1, foreground='w'), mpatheffects.Normal()]

    def gridvalue(self, data, num=20, fmt='{:.0f}', color='b', fontsize=None,
            stroke=False, maskValue=None, onlyLand=False, zorder=4, **kwargs):
        if fontsize is None:
            fontsize = self.fontsize['gridvalue']
        if stroke:
            kwargs.update(path_effects=self._get_stroke_patheffects())
        step = self.stepcal(num)
        if step == 0: step = 1
        kwargs.update(color=color, fontsize=fontsize, ha='center', va='center',
                      family=self.family, transform=ccrs.PlateCarree(),
                      zorder=zorder)
        if onlyLand:
            from mpl_toolkits.basemap import Basemap
            m = Basemap(ax=self.ax, projection='cyl', resolution='c',
                        llcrnrlat=self.latmin, urcrnrlat=self.latmax,
                        llcrnrlon=self.lonmin, urcrnrlon=self.lonmax)
        if not self.no_parameri:
            meri, para = len(self.y), len(self.x)
            for i in range(1, meri-1, step):
                for j in range(1, para-1, step):
                    lon, lat = _x = self.xx[i][j], self.yy[i][j]
                    if onlyLand and not m.is_land(lon, lat):
                        continue
                    if isinstance(data[i][j], np.ma.core.MaskedConstant) or np.isnan(data[i][j]):
                        continue
                    if not maskValue is None:
                        if not fmt.format(data[i][j]) == str(maskValue):
                            self.ax.text(lon, lat, fmt.format(data[i][j]), **kwargs)
                    else:
                        self.ax.text(lon, lat, fmt.format(data[i][j]), **kwargs)
        else:
            x1, x2, y1, y2 = self.ax.get_extent()
            deltax, deltay = x2 - x1, y2 - y1
            x1 += 0.02 * deltax
            x2 -= 0.02 * deltax
            y1 += 0.02 * deltay
            y2 -= 0.02 * deltay
            x = np.linspace(x1, x2, num)
            y = np.linspace(y1, y2, num)
            xx, yy = np.meshgrid(x, y)
            points = ccrs.Geodetic().transform_points(self.ax.projection, xx, yy)
            if self.xx[self.xx < 0].size == 0:
                points[:,:,0][points[:,:,0] < 0] += 360
            points_round = np.round(points / self.res) * self.res
            lon_points, lat_points = points_round[:,:,0], points_round[:,:,1]
            for i in range(lon_points.shape[0]):
                for j in range(lat_points.shape[1]):
                    lon, lat = lon_points[i, j], lat_points[i, j]
                    if onlyLand and not m.is_land(lon, lat):
                        continue
                    # calculate nearest index
                    distances = np.sqrt((self.xx - lon) ** 2 + (self.yy - lat) ** 2)
                    nearest_idx = np.unravel_index(np.argmin(distances), distances.shape)
                    value = data[nearest_idx]
                    if isinstance(value, np.ma.core.MaskedConstant) or np.isnan(value):
                        continue
                    if not maskValue is None:
                        if not fmt.format(value) == str(maskValue):
                            self.ax.text(lon, lat, fmt.format(value), **kwargs)
                    else:
                        self.ax.text(lon, lat, fmt.format(value), **kwargs)

    def marktext(self, x, y, text='', mark='×', textpos='right', stroke=False,
            bbox=None, family='plotplus', markfontsize=None, **kwargs):
        bbox = bbox or {}
        if family == 'plotplus':
            kwargs.update(family=self.family)
        elif family is not None:
            kwargs.update(family=family)
        if not markfontsize:
            markfontsize = self.fontsize['mmfilter']
        fontsize = kwargs.pop('fontsize', self.fontsize['marktext'])
        if stroke:
            kwargs.update(path_effects=self._get_stroke_patheffects())
        if 'zorder' not in kwargs:
            kwargs.update(zorder=4)
        bbox = merge_dict(bbox, {'facecolor':'none', 'edgecolor':'none'})
        xy, xytext, ha, va=dict(right=((1, 0.5), (2, 0), 'left', 'center'),
                                left=((0, 0.5), (-2, 0), 'right', 'center'),
                                top=((0.5, 1), (0, 1), 'center', 'bottom'),
                                bottom=((0.5, 0), (0, -1), 'center', 'top')).get(textpos)
        an_mark = self.ax.annotate(mark, xy=(x,y), va='center', ha='center', bbox=bbox,
            xycoords=ccrs.PlateCarree()._as_mpl_transform(self.ax), fontsize=markfontsize,
            **kwargs)
        an_text = self.ax.annotate(text, xy=xy, xycoords=an_mark, xytext=xytext,
            textcoords='offset points', va=va, ha=ha, bbox=bbox, fontsize=fontsize,
            **kwargs)
        an_mark.set_clip_path(self.ax.patch)
        an_text.set_clip_path(self.ax.patch)
        return an_mark, an_text

    def maxminfilter(self, data, type='min', fmt='{:.0f}', weight='bold', color='b',
            fontsize=None, window=25, vmin=-1e7, vmax=1e7, stroke=False, marktext=False,
            marktextdict=None, zorder=4, **kwargs):
        '''Use res keyword or ip keyword to interpolate'''
        marktextdict = marktextdict or {}
        if fontsize is None:
            fontsize = self.fontsize['mmfilter']
        if stroke:
            kwargs.update(path_effects=self._get_stroke_patheffects())
        textfunc = self.ax.text
        kwargs.update(fontweight=weight, color=color, fontsize=fontsize, ha='center',
            va='center', transform=ccrs.PlateCarree(), zorder=zorder)
        if marktext:
            argsdict = dict(fontsize=fontsize, weight=weight, color=color, stroke=stroke,
                markfontsize=8, family=None, textpos='bottom')
            kwargs = merge_dict(marktextdict, argsdict)
            textfunc = self.marktext
        xx, yy = self.xx, self.yy
        if 'ip' in kwargs:
            ip = kwargs.pop('ip')
            xx, yy, data = self.interpolation(data, ip)
        if type == 'min':
            ftr = snd.minimum_filter
        elif type == 'max':
            ftr = snd.maximum_filter
        else:
            raise PlotError('Unsupported filter type!')
        dataftr = ftr(data, window, mode='nearest')
        yind, xind = np.where(data == dataftr)
        ymax, xmax = data.shape
        for y, x in zip(yind, xind):
            d = data[y, x]
            _x = xx[y, x]
            _y = yy[y, x]
            if d < vmax and d > vmin and x not in (0, xmax-1) and y not in (0, ymax-1):
                if isinstance(d, np.ma.core.MaskedConstant) or np.isnan(d):
                    continue
                textfunc(_x, _y, fmt.format(d), **kwargs)

    def boxtext(self, s, textpos='upper left', bbox={}, color='k', fontsize=None, **kwargs):
        if fontsize is None:
            fontsize = self.fontsize['boxtext']
        supported_positions = {
            'upper left': (0.01, 0.99, 'left', 'top'),
            'upper center': (0.5, 0.99, 'center', 'top'),
            'upper right': (0.01, 0.99, 'right', 'top'),
            'lower left': (0.01, 0.01, 'left', 'bottom'),
            'lower center': (0.5, 0.01, 'center', 'bottom'),
            'lower right': (0.99, 0.01, 'right', 'bottom')
        }
        if textpos not in supported_positions:
            raise PlotError('Unsupported position {}.'.format(textpos))
        x, y, ha, va = supported_positions[textpos]
        bbox = merge_dict(bbox, {'boxstyle':'round', 'facecolor':'w', 'pad':0.4,
            'edgecolor':'none'})
        kwargs = merge_dict(kwargs, {'family':self.family})
        t = self.ax.text(x, y, s, bbox=bbox, va=va, ha=ha, fontsize=fontsize,
            color=color, transform=self.ax.transAxes, **kwargs)
        return t

    def title(self, s):
        self.ax.text(0, 1.039, s, transform=self.ax.transAxes, fontsize=self.fontsize['title'],
            family=self.family)

    def set_title(self, s, **kwargs):
        self.ax.text(0, 1.039, s, transform=self.ax.transAxes, **kwargs)

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
                fromhour, tohour, fromtime.strftime(stdfmt), totime.strftime(stdfmt))
        self._timestamp(s)

    def _timestamp(self, s):
        self.ax.text(0, 1.01, s, transform=self.ax.transAxes,
            fontsize=self.fontsize['timestamp'], family=self.family)

    def _timestamp_custom(self, s, **kwargs):
        self.ax.text(0, 1.01, s, transform=self.ax.transAxes, **kwargs)

    def _colorbar_unit(self, s):
        if not s:
            return
        self.ax.text(1.05, 1.01, s, transform=self.ax.transAxes, ha='right',
            fontsize=self.fontsize['timestamp'], family=self.family)

    def maxminnote(self, data, name, unit='', type='max', fmt='{:.1f}'):
        type = type.lower()
        if type == 'max':
            typestr = 'Max.'
            notevalue = np.nanmax(data)
        elif type == 'min':
            typestr = 'Min.'
            notevalue = np.nanmin(data)
        elif type == 'mean':
            typestr = 'Mean'
            notevalue = np.nanmean(data)
        else:
            raise PlotError('Unsupported type!')
        notestr = '{:s} {:s}: '.format(typestr, name) + fmt.format(notevalue) + ' ' + unit
        if self.mmnote != '':
            self.mmnote = self.mmnote + ' | ' + notestr
        else:
            self.mmnote = notestr

    def _maxminnote(self, s):
        self.mmnote = s

    def footernote(self, s):
        y_footer = -0.02 if self.no_parameri else -0.036
        self.ax.text(0, y_footer, s, va='top', ha='left', color='red', transform=self.ax.transAxes,
            fontsize=self.fontsize['footer'], family=self.family)

    def _set_note(self, s, **kwargs):
        self.ax.text(1, 1.01, s, ha='right', transform=self.ax.transAxes, **kwargs)

    def stdsave(self, directory, basetime, fcsthour, imcode):
        if isinstance(basetime, str):
            basetime = datetime.strptime(basetime, '%Y%m%d%H')
        path = os.path.join(directory, '%s_%s_%d_%d%d%d%d.png' % \
            (basetime.strftime('%Y%m%d%H'), imcode, fcsthour, self.latmin,
            self.latmax, self.lonmin, self.lonmax))
        self.save(path)

    def save(self, path, **kwargs):
        if not self.mmnote == "": 
            self.ax.text(1, 1.01, self.mmnote, ha='right', transform=self.ax.transAxes,
                fontsize=self.fontsize['mmnote'], family=self.family)
        self.ax.axis('off')
        if self.inside_axis:
            self.fig.subplots_adjust(bottom=0, top=1, left=0, right=1)
            self.fig.savefig(path, dpi=self.dpi, pad_inches=0., **kwargs)
        else:
            self.fig.savefig(path, dpi=self.dpi, bbox_inches='tight', edgecolor='none',
                pad_inches=0.04, **kwargs)

    def close(self):
        self.ax.clear()
        self.fig.clear()
        plt.close(self.fig)
        plt.close("all")
        # 显式释放
        del self.ax, self.fig
        gc.collect()
    
    def closeAxis(self):
        plt.axis('off')


def merge_dict(a, b):
    '''Merge B into A without overwriting A'''
    for k, v in b.items():
        if k not in a:
            a[k] = v
    return a


class MapSet:
    """Portable mapset for small area and high resolution data plotting.
    The default Cartopy features (e.g. coastlines, borders) are not scalable
    geographically. If we want to plot something in a small georange,
    naturally we need high-res features to avoid coarseness. Also, every time
    when we add features on a plot, Cartopy will calculate which geometries
    are in the given georange and can be plotted, which cost noticeable time.
    As a result if we plot many figures on the same small georange, many time
    and computing power are wasted.
    To address this problem I create a reusable mapset for Cartopy. It will
    calculate desired geometries upon initiating, which is reusable and fully
    compatible with Cartopy functions. It can also be saved as a file by
    pickle, further reducing overhead time.
    Example code:
    ```
    georange = 15, 35, 110, 135
    mapset = MapSet(proj=ccrs.PlateCarree(), georange=georange)
    mapset.coastline = PartialNaturalEarthFeature('physical', 'coastline',
        '10m', georange=georange)
    p = Plot()
    p.usemapset(mapset)
    p.drawcoastlines()
    ```
    or, more easily:
    ```
    georange = 15, 35, 110, 135
    mapset = MapSet.from_natural_earth(proj='P', georange=georange)
    p.usemapset(mapset)
    """

    def __init__(self, proj=None, georange=None, coastline=None, country=None,
            land=None, ocean=None, province=None, city=None, county=None,
            scale=None, proj_params=None):
        self.proj = proj
        self.georange = georange
        self.scale = scale
        self.coastline = coastline
        self.country = country
        self.land = land
        self.ocean = ocean
        self.province = province
        self.city = city
        self.county = county
        self.proj_params = proj_params

    @classmethod
    def from_natural_earth(cls, georange=None, scale='50m', proj='P',
            coastline=True, country=True, land=False, ocean=False, proj_params=None):
        ins = cls(proj=proj, georange=georange, scale=scale, proj_params=proj_params)
        if coastline:
            ins.coastline = PartialNaturalEarthFeature('physical', 'coastline',
                scale, georange=georange)
        if country:
            ins.country = PartialNaturalEarthFeature('cultural',
                'admin_0_boundary_lines_land', scale, georange=georange)
        if land:
            ins.land = PartialNaturalEarthFeature('physical', 'land', scale,
                georange=georange)
        if ocean:
            ins.ocean = PartialNaturalEarthFeature('physical', 'ocean',
                scale, georange=georange)
        return ins

    @classmethod
    def load(cls, filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)

    def save(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self, f)


class PartialShapelyFeature(cfeature.ShapelyFeature):

    def __init__(self, *args, georange=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.extent = georange[2:] + georange[:2]
        self.make_partial()

    def intersecting_geometries(self, extent):
        return self.geometries()

    def make_partial(self):
        if self.extent[0] < 180 < self.extent[1]:
            extent1 = self.extent[0], 180., self.extent[2], self.extent[3]
            extent2 = (-180., self.extent[1] - 360.,
                self.extent[2], self.extent[3])
            self._geoms = list(super().intersecting_geometries(extent1)) +\
                list(super().intersecting_geometries(extent2))
        else:
            self._geoms = list(super().intersecting_geometries(self.extent))

    @classmethod
    def from_shp(cls, directory, georange=None, **kwargs):
        feature = cls(ciosr.Reader(directory).geometries(),
            ccrs.PlateCarree(), georange=georange, **kwargs)
        return feature


class PartialNaturalEarthFeature(cfeature.NaturalEarthFeature):

    def __init__(self, *args, georange=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.extent = georange[2:] + georange[:2]
        self._geoms = ()
        self.make_partial()

    def intersecting_geometries(self, extent):
        return self.geometries()

    def geometries(self):
        return iter(self._geoms)

    def make_partial(self):
        path = ciosr.natural_earth(resolution=self.scale,
            category=self.category, name=self.name)
        self._geoms = tuple(ciosr.Reader(path).geometries())
        if self.extent[0] < 180 < self.extent[1]:
            extent1 = self.extent[0], 180., self.extent[2], self.extent[3]
            extent2 = (-180., self.extent[1] - 360.,
                self.extent[2], self.extent[3])
            self._geoms = list(super().intersecting_geometries(extent1)) +\
                list(super().intersecting_geometries(extent2))
        else:
            self._geoms = list(super().intersecting_geometries(self.extent))
