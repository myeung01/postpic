#
# This file is part of postpic.
#
# postpic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# postpic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with postpic. If not, see <http://www.gnu.org/licenses/>.
#
# Stephan Kuschel 2014
"""
Particle related routines.
"""

__all__ = ['ParticleAnalyzer']

import numpy as np
from analyzer import PhysicalConstants as pc
import analyzer
from ..datahandling import *

identifyspecies = analyzer.SpeciesIdentifier.identifyspecies


class _SingleSpeciesAnalyzer(object):
    """
    used by the ParticleAnalyzer class only.
    The _SingleSpeciesAnalyzer will return atomic particle properties
    (see list below) as given by the dumpreader. Each property can thus
    return
    1) a list (one value for each particle)
    2) a siingle scalar value if this property is equal for the entire
    species (as usual for 'mass' or 'charge').
    3) raise a KeyError on request if the property wasnt dumped.
    """
    # List of atomic particle properties. Those will be requested from the dumpreader
    # All other particle properties will be calculated from these.
    _atomicprops = ['weight', 'X', 'Y', 'Z', 'Px', 'Py', 'Pz', 'mass', 'charge', 'ID']

    def __init__(self, dumpreader, species):
        self.species = species
        self._dumpreader = dumpreader
        self.uncompress()
        # Variables will be read and added to self._cache when needed.

        # create a method for every _atomicprops item.
        def makefunc(_self, key):
            def ret(_self):
                return _self._readatomic(key)
            return ret
        for key in self._atomicprops:
            setattr(_SingleSpeciesAnalyzer, key, makefunc(self, key))

    def _readatomic(self, key):
        '''
        Reads an atomic property, thus one out of
        weight, x, y, z, px, py, pz, mass, charge, ID
        (self._atomicprops)
        '''
        if key in self._cache:
            ret = self._cache[key]
        else:
            if key in ['mass', 'charge']:
                try:
                    ret = self._dumpreader.getSpecies(self.species, key)
                except(KeyError):
                    # in the special case of mass or charge try to deduce mass or charge
                    # from the species name.
                    self._idfy = identifyspecies(self.species)
                    ret = self._idfy[key]
            else:
                ret = self._dumpreader.getSpecies(self.species, key)
            ret = np.float64(ret)
            if isinstance(ret, float):  # cache single scalars always
                self._cache[key] = ret
            if isinstance(ret, np.ndarray) and self._compressboollist is not None:
                ret = ret[self._compressboollist]  # avoid executing this line too often.
                self._cache[key] = ret
                # if memomry is low, caching could be skipped entirely.
                # See commit message for benchmark.
        return ret

    def compress(self, condition, name='unknown condition'):
        """
        works like numpy.compress.
        Additionaly you can specify a name, that gets saved in the compresslog.

        condition has to be one out of:
        1)
        condition =  [True, False, True, True, ... , True, False]
        condition is a list of length N, specifing which particles to keep.
        Example:
        cfintospectrometer = lambda x: x.angle_offaxis() < 30e-3
        cfintospectrometer.name = '< 30mrad offaxis'
        pa.compress(cfintospectrometer(pa), name=cfintospectrometer.name)
        2)
        condtition = [1, 2, 4, 5, 9, ... , 805, 809]
        condition can be a list of arbitraty length, so only the particles
        with the ids listed here are kept.
        """
        if np.array(condition).dtype is np.dtype('bool'):
            # Case 1:
            # condition is list of boolean values specifying particles to use
            assert len(self) == len(condition), \
                'number of particles ({:7n}) has to match' \
                'length of condition ({:7n})' \
                ''.format(len(self), len(condition))
            if self._compressboollist is None:
                self._compressboollist = condition
            else:
                self._compressboollist[self._compressboollist] = condition
            for key in self._cache:
                if isinstance(self._cache[key], np.ndarray):
                    self._cache[key] = self._cache[key][condition]
            self.compresslog = np.append(self.compresslog, name)
        else:
            # Case 2:
            # condition is list of particle IDs to use
            condition = np.array(condition, dtype='int')
            # same as
            # bools = np.array([idx in condition for idx in self._ID])
            # but benchmarked to be 1500 times faster :)
            condition.sort()
            idx = np.searchsorted(condition, self._ID)
            idx[idx == len(condition)] = 0
            bools = condition[idx] == self._ID
            self.compress(bools, name=name)

    def uncompress(self):
        """
        Discard all previous runs of 'compress'
        """
        self.compresslog = []
        self._compressboollist = None
        self._cache = {}

    # --- Only very basic functions

    def __len__(self):  # = number of particles
        # find a valid dataset to count number of paricles
        if self._compressboollist is not None:
            return np.count_nonzero(self._compressboollist)
        for key in self._atomicprops:
            try:
                # len(3) will yield a TypeError, len([3]) returns 1
                ret = len(self._readatomic(key))
                break
            except(TypeError, KeyError):
                pass
        return ret

    # calculate new per particle properties from the atomic properties.
    # the following functions can be computed more efficiently here
    # than in the ParticleAnalyzer.
    # (example: if mass is constant for the entire species, it doesnt
    # have to be repeated using np.repeat before the calculation)

    def gamma(self):
        return np.sqrt(1 +
                       (self.Px() ** 2 + self.Py() ** 2 + self.Pz() ** 2)
                       / (self.mass() * pc.c) ** 2)

    def mass_u(self):
        return self.mass() / pc.mass_u

    def charge_e(self):
        return self.charge() / pc.qe

    def Eruhe(self):
        return self.mass() * pc.c ** 2

    def Ekin(self):
        return (self.gamma() - 1) * self.Eruhe()

    def Ekin_MeV(self):
        return self.Ekin() / pc.qe / 1e6

    def Ekin_MeV_amu(self):
        return self.Ekin_MeV() / self.mass_u()

    def Ekin_MeV_qm(self):
        return self.Ekin_MeV() * self.charge_e() / self.mass_u()

    def Ekin_keV(self):
        return self.Ekin() / pc.qe / 1e3

    def Ekin_keV_amu(self):
        return self.Ekin_keV() / self.mass_u()

    def Ekin_keV_qm(self):
        return self.Ekin_MeV() * self.charge_e() / self.mass_u()


class ParticleAnalyzer(object):
    """
    The ParticleAnalyzer class. Different ParticleAnalyzer can be
    added together to create a combined collection.

    The ParticleAnalyzer will return a list of values for every
    particle property.
    """

    def __init__(self, dumpreader, *speciess):
        # create 'empty' ParticleAnalyzer
        self._ssas = []
        self._species = None  # trivial name if set
        self._compresslog = []
        self.simdimensions = dumpreader.simdimensions()
        try:
            self.X.__func__.extent = dumpreader.extent('x')
            self.X.__func__.gridpoints = dumpreader.gridpoints('x')
            self.X_um.__func__.extent = dumpreader.extent('x') * 1e6
            self.X_um.__func__.gridpoints = dumpreader.gridpoints('x')
            self.Y.__func__.extent = dumpreader.extent('y')
            self.Y.__func__.gridpoints = dumpreader.gridpoints('y')
            self.Y_um.__func__.extent = dumpreader.extent('y') * 1e6
            self.Y_um.__func__.gridpoints = dumpreader.gridpoints('y')
            self.Z.__func__.extent = dumpreader.extent('z')
            self.Z.__func__.gridpoints = dumpreader.gridpoints('z')
            self.Z_um.__func__.extent = dumpreader.extent('z') * 1e6
            self.Z_um.__func__.gridpoints = dumpreader.gridpoints('z')
        except(KeyError):
            pass
        self.angle_xy.__func__.extent = np.real([-np.pi, np.pi])
        self.angle_yz.__func__.extent = np.real([-np.pi, np.pi])
        self.angle_zx.__func__.extent = np.real([-np.pi, np.pi])
        # add particle species one by one
        for s in speciess:
            self.add(dumpreader, s)

    def __str__(self):
        return '<ParticleAnalyzer including ' + str(self.species) \
            + '(' + str(len(self)) + ')>'

    @property
    def npart(self):
        '''
        Number of Particles.
        '''
        ret = 0
        for ssa in self._ssas:
            ret += len(ssa)
        return ret

    @property
    def nspecies(self):
        return len(self._ssas)

    def __len__(self):
        return self.npart

    @property
    def species(self):
        '''
        returns an string name for the species involved.
        Basically only returns unique names from all species
        (used for plotting and labeling purposes -- not for completeness).
        May be overwritten.
        '''
        if self._species is not None:
            return self._species
        ret = ''
        for s in set(self.speciess):
            ret += s + ' '
        ret = ret[0:-1]
        return ret

    @species.setter
    def species(self, name):
        self._name = name

    @property
    def name(self):
        '''
        an alias to self.species
        '''
        return self.species

    @property
    def speciess(self):
        '''
        a complete list of all species involved.
        '''
        return [ssa.species for ssa in self._ssas]

    def add(self, dumpreader, species):
        '''
        adds species to this analyzer.

        Attributes
        ----------
        species can be a single species name
                or a reserved name for collection of species, such as
                ions    adds all available particles that are ions
                nonions adds all available particles that are not ions
                ejected
                noejected
                all
        '''
        keys = {'ions': lambda s: identifyspecies(s)['ision'],
                'nonions': lambda s: not identifyspecies(s)['ision'],
                'ejected': lambda s: identifyspecies(s)['ejected'],
                'noejected': lambda s: not identifyspecies(s)['ejected'],
                'all': lambda s: True}
        if species in keys:
            ls = dumpreader.listSpecies()
            toadd = [s for s in ls if keys[species](s)]
            for s in toadd:
                self.add(dumpreader, s)
        else:
            self._ssas.append(_SingleSpeciesAnalyzer(dumpreader, species))
        return

    # --- Operator overloading

    def __add__(self, other):  # self + other
        ret = copy.copy(self)
        ret += other
        return ret

    def __iadd__(self, other):  # self += other
        '''
        adding ParticleAnalyzers should give the feeling as if you were adding
        their particle lists. Thats why there is no append function.
        Compare those outputs (numpy.array handles that differently!):
        a=[1,2,3]; a.append([4,5]); print a
        [1,2,3,[4,5]]
        a=[1,2,3]; a += [4,5]; print a
        [1,2,3,4,5]
        '''
        # only add ssa with more than 0 particles.
        for ssa in other._ssas:
            if len(ssa) > 0:
                self._ssas.append(copy.copy(ssa))
        return self

    # --- compress related functions ---

    def compress(self, condition, name='unknown condition'):
        i = 0
        for ssa in self._ssas:  # condition is list of booleans
            if condition.dtype == np.dtype('bool'):
                n = ssa.weight().shape[0]
                ssa.compress(condition[i:i + n], name=name)
                i += n
            else:  # condition is list of particle IDs
                ssa.compress(condition, name=name)
        self._compresslog = np.append(self._compresslog, name)

    # --- user friendly functions

    def compressfn(self, conditionf, name='unknown condition'):
        if hasattr(conditionf, 'name'):
            name = conditionf.name
        self.compress(conditionf(self), name=name)

    def uncompress(self):
        self._compresslog = []
        for s in self._ssas:
            s.uncompress()

    def getcompresslog(self):
        ret = {'all': self._compresslog}
        for ssa in self._ssas:
            ret.update({ssa.species: ssa.compresslog})
        return ret

    # --- map functions to SingleSpeciesAnalyzer

    def _map2ssa(self, func):
        '''
        maps a function to the SingleSpeciesAnalyzers. If the SingleSpeciesAnalyzer
        returns a single scalar, it will be repeated using np.repeat to ensure
        that a list will always be returned.
        '''
        ret = np.array([])
        for ssa in self._ssas:
            a = getattr(ssa, func)()
            if isinstance(a, float):
                a = np.repeat(a, len(ssa))
            ret = np.append(ret, a)
        return ret

    # --- "A scalar for every particle"-functions.

    def weight(self):
        return self._map2ssa('weight')
    weight.name = 'Particle weight'
    weight.unit = 'npartpermacro'

    def ID(self):
        ret = self._map2ssa('ID')
        return np.array(ret, type=int)

    def mass(self):  # SI
        return self._map2ssa('mass')
    mass.unit = 'kg'
    mass.name = 'm'

    def mass_u(self):
        return self._map2ssa('mass_u')
    mass_u.unit = 'u'
    mass_u.name = 'm'

    def charge(self):  # SI
        return self._map2ssa('charge')
    charge.unit = 'C'
    charge.name = 'q'

    def charge_e(self):
        return self._map2ssa('charge_e')
    charge.unit = 'qe'
    charge.name = 'q'

    def Eruhe(self):
        return self._map2ssa('Eruhe')

    def Px(self):
        return self._map2ssa('Px')
    Px.unit = ''
    Px.name = 'Px'

    def Py(self):
        return self._map2ssa('Py')
    Py.unit = ''
    Py.name = 'Py'

    def Pz(self):
        return self._map2ssa('Pz')
    Pz.unit = ''
    Pz.name = 'Pz'

    def P(self):
        return np.sqrt(self.Px() ** 2 + self.Py() ** 2 + self.Pz() ** 2)
    P.unit = ''
    P.name = 'P'

    def X(self):
        return self._map2ssa('X')
    X.unit = 'm'
    X.name = 'X'

    def X_um(self):
        return self.X() * 1e6
    X_um.unit = '$\mu m$'
    X_um.name = 'X'

    def Y(self):
        return self._map2ssa('Y')
    Y.unit = 'm'
    Y.name = 'Y'

    def Y_um(self):
        return self.Y() * 1e6
    Y_um.unit = '$\mu m$'
    Y_um.name = 'Y'

    def Z(self):
        return self._map2ssa('Z')
    Z.unit = 'm'
    Z.name = 'Z'

    def Z_um(self):
        return self.Z() * 1e6
    Z_um.unit = '$\mu m$'
    Z_um.name = 'Z'

    def beta(self):
        return np.sqrt(self.gamma() ** 2 - 1) / self.gamma()
    beta.unit = r'$\beta$'
    beta.name = 'beta'

    def V(self):
        return pc.c * self.beta()
    V.unit = 'm/s'
    V.name = 'V'

    def gamma(self):
        return self._map2ssa('gamma')
    gamma.unit = r'$\gamma$'
    gamma.name = 'gamma'

    def Ekin(self):
        return self._map2ssa('Ekin')
    Ekin.unit = 'J'
    Ekin.name = 'Ekin'

    def Ekin_MeV(self):
        return self._map2ssa('Ekin_MeV')
    Ekin_MeV.unit = 'MeV'
    Ekin_MeV.name = 'Ekin'

    def Ekin_MeV_amu(self):
        return self._map2ssa('Ekin_MeV_amu')
    Ekin_MeV_amu.unit = 'MeV / amu'
    Ekin_MeV_amu.name = 'Ekin / amu'

    def Ekin_MeV_qm(self):
        return self._map2ssa('Ekin_MeV_qm')
    Ekin_MeV_qm.unit = 'MeV*q/m'
    Ekin_MeV_qm.name = 'Ekin * q/m'

    def Ekin_keV(self):
        return self._map2ssa('Ekin_keV')
    Ekin_keV.unit = 'keV'
    Ekin_keV.name = 'Ekin'

    def Ekin_keV_amu(self):
        return self._map2ssa('Ekin_keV_amu')
    Ekin_keV_amu.unit = 'keV / amu'
    Ekin_keV_amu.name = 'Ekin / amu'

    def Ekin_keV_qm(self):
        return self._map2ssa('Ekin_keV_qm')
    Ekin_keV_qm.unit = 'keV*q/m'
    Ekin_keV_qm.name = 'Ekin * q/m'

    def angle_xy(self):
        return np.arctan2(self.Py(), self.Px())
    angle_xy.unit = 'rad'
    angle_xy.name = 'anglexy'

    def angle_yz(self):
        return np.arctan2(self.Pz(), self.Py())
    angle_yz.unit = 'rad'
    angle_yz.name = 'angleyz'

    def angle_zx(self):
        return np.arctan2(self.Px(), self.Pz())
    angle_zx.unit = 'rad'
    angle_zx.name = 'anglezx'

    def angle_yx(self):
        return np.arctan2(self.Px(), self.Py())
    angle_yx.unit = 'rad'
    angle_yx.name = 'angleyx'

    def angle_zy(self):
        return np.arctan2(self.Py(), self.Pz())
    angle_zy.unit = 'rad'
    angle_zy.name = 'anglezy'

    def angle_xz(self):
        return np.arctan2(self.Pz(), self.Px())
    angle_xz.unit = 'rad'
    angle_xz.name = 'anglexz'

    def angle_xaxis(self):
        return np.arctan2(np.sqrt(self.Py()**2 + self.Pz()**2), self.Px())
    angle_xaxis.unit = 'rad'
    angle_xaxis.name = 'angle_xaxis'

    # ---- Functions to create a Histogram. ---

    def createHistgram1d(self, scalarfx, optargsh={'bins': 300},
                         simextent=False, simgrid=False, rangex=None,
                         weights=lambda x: 1):
        if simgrid:
            simextent = True
        xdata = scalarfx(self)
        # In case there are no particles
        if len(xdata) == 0:
            return [], []
        if rangex is None:
            rangex = [np.min(xdata), np.max(xdata)]
        if simextent:
            if hasattr(scalarfx, 'extent'):
                rangex = scalarfx.extent
        if simgrid:
            if hasattr(scalarfx, 'gridpoints'):
                optargsh['bins'] = scalarfx.gridpoints
        w = self.weight() * weights(self)
        h, edges = np.histogram(xdata, weights=w,
                                range=rangex, **optargsh)
        h = h / np.diff(edges)  # to calculate particles per xunit.
        return h, edges

    def createHistgram2d(self, scalarfx, scalarfy,
                         optargsh={'bins': [500, 500]}, simextent=False,
                         simgrid=False, rangex=None, rangey=None,
                         weights=lambda x: 1):
        """
        Creates an 2d Histogram.

        Attributes
        ----------
        scalarfx : function
            returns a list of scalar values for the x axis.
        scalarfy : function
            returns a list of scalar values for the y axis.
        simgrid : boolean, optional
            enforces the same grid as used in the simulation.
            Implies simextent=True. Defaults to False.
        simextent : boolean, optional
            enforces, that the axis show the same extent as used in the
            simulation. Defaults to False.
        weights : function, optional
            applies additional weights to the macroparticles, for example
            "ParticleAnalyzer.Ekin_MeV"".
            Defaults to "lambda x:1".
        """
        if simgrid:
            simextent = True
        xdata = scalarfx(self)
        ydata = scalarfy(self)
        if len(xdata) == 0:
            return [[]], [0, 1], [1]
        # TODO: Falls rangex oder rangy gegeben ist,
        # ist die Gesamtteilchenzahl falsch berechnet, weil die Teilchen die
        # ausserhalb des sichtbaren Bereiches liegen mitgezaehlt werden.
        if rangex is None:
            rangex = [np.min(xdata), np.max(xdata)]
        if rangey is None:
            rangey = [np.min(ydata), np.max(ydata)]
        if simextent:
            if hasattr(scalarfx, 'extent'):
                rangex = scalarfx.extent
            if hasattr(scalarfy, 'extent'):
                rangey = scalarfy.extent
        if simgrid:
            if hasattr(scalarfx, 'gridpoints'):
                optargsh['bins'][0] = scalarfx.gridpoints
            if hasattr(scalarfy, 'gridpoints'):
                optargsh['bins'][1] = scalarfy.gridpoints
        w = self.weight() * weights(self)  # Particle Size * additional weights
        h, xedges, yedges = np.histogram2d(xdata, ydata,
                                           weights=w, range=[rangex, rangey],
                                           **optargsh)
        h = h / (xedges[1] - xedges[0]) / (yedges[1] - yedges[0])
        return h, xedges, yedges

    def createHistgramField1d(self, scalarfx, name='distfn', title=None,
                              **kwargs):
        """
        Creates an 1d Histogram enclosed in a Field object.

        Attributes
        ----------
        scalarfx : function
            returns a list of scalar values for the x axis.
        name : string, optional
            addes a name. usually used for generating savenames.
            Defaults to "distfn".
        title: string, options
            overrides the title. Autocreated if title==None.
            Defaults to None.
        **kwargs
            given to createHistgram1d.
        """
        if 'weights' in kwargs:
            name = kwargs['weights'].name
        h, edges = self.createHistgram1d(scalarfx, **kwargs)
        ret = Field(h, edges)
        ret.axes[0].grid_node = edges
        ret.name = name + ' ' + self.species
        ret.label = self.species
        if title:
            ret.name = title
        if hasattr(scalarfx, 'unit'):
            ret.axes[0].unit = scalarfx.unit
        if hasattr(scalarfx, 'name'):
            ret.axes[0].name = scalarfx.name
        ret.infos = self.getcompresslog()['all']
        ret.infostring = self.npart
        return ret

    def createHistgramField2d(self, scalarfx, scalarfy, name='distfn',
                              title=None, **kwargs):
        """
        Creates an 2d Histogram enclosed in a Field object.

        Attributes
        ----------
        scalarfx : function
            returns a list of scalar values for the x axis.
        scalarfy : function
            returns a list of scalar values for the y axis.
        name : string, optional
            addes a name. usually used for generating savenames.
            Defaults to "distfn".
        title: string, options
            overrides the title. Autocreated if title==None.
            Defaults to None.
        **kwargs
            given to createHistgram2d.
        """
        if 'weights' in kwargs:
            name = kwargs['weights'].name
        h, xedges, yedges = self.createHistgram2d(scalarfx, scalarfy, **kwargs)
        ret = Field(h, xedges, yedges)
        ret.axes[0].grid_node = xedges
        ret.axes[1].grid_node = yedges
        ret.name = name + self.species
        ret.label = self.species
        if title:
            ret.name = title
        ret.axes[0].unit = scalarfx.unit
        ret.axes[0].name = scalarfx.name
        ret.axes[1].unit = scalarfy.unit
        ret.axes[1].name = scalarfy.name
        ret.infostring = '{:.0f} npart in {:.0f} species'.format(self.npart, self.nspecies)
        ret.infos = self.getcompresslog()['all']
        return ret

    def createField(self, *scalarf, **kwargs):
        """
        Creates an n-d Histogram enclosed in a Field object.
        Try using this function first.

        Attributes
        ----------
        *args
            list of scalarfunctions that should be used for the axis.
            the number of args given determins the dimensionality of the
            field returned by this function.
        **kwargs
            given to createHistgram1d or createHistgram2d.
        """
        if self.simdimensions is None:
            return None
        if len(scalarf) == 1:
            return self.createHistgramField1d(*scalarf, **kwargs)
        elif len(scalarf) == 2:
            return self.createHistgramField2d(*scalarf, **kwargs)
        else:
            raise Exception('only 1d or 2d field creation implemented yet.')


