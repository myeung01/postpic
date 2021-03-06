#!/usr/bin/env python2

import numpy as np
import postpic as pp

# postpic will use matplotlib for plotting. Changing matplotlibs backend
# to "Agg" makes it possible to save plots without a display attached.
# This is necessary to run this example within the "run-tests" script
# on travis-ci.
import matplotlib; matplotlib.use('Agg')


# choose the dummy reader. This reader will create fake data for testing.
pp.datareader.chooseCode('dummy')

dr = pp.datareader.readDump(3e5)  # Dummyreader takes a float as argument, not a string.
# set and create directory for pictures.
savedir = '_examplepictures/'
import os
if not os.path.exists(savedir):
    os.mkdir(savedir)

# initialze the plotter object.
# project name will be prepended to all output names
plotter = pp.plotting.plottercls(dr, outdir=savedir, autosave=True, project='simpleexample')

# create the field analyzer to access field data (E and B fields) easily
fa = pp.analyzer.FieldAnalyzer(dr)

# we will need a refrence to the ParticleAnalyzer quite often
from postpic.analyzer import ParticleAnalyzer as PA

# create ParticleAnalyzer for every particle species that exists.
pas = [PA(dr, s) for s in dr.listSpecies()]

if True:
    # Plot Data from the FieldAnalyzer fa. This is very simple: every line creates one plot
    plotter.plotField(fa.Ex())  # plot 0
    plotter.plotField(fa.Ey())  # plot 1
    plotter.plotField(fa.Ez())  # plot 2
    plotter.plotField(fa.energydensityEM())  # plot 3

    # Using the ParticleAnalyzer requires an additional step:
    # 1) The ParticleAnalyzer.createField method will be used to create a Field object
    # with choosen particle scalars on every axis
    # 2) Plot the Field objecton
    optargsh={'bins': [300,300]}
    for pa in pas:
        # create a Field object nd holding the number density
        nd = pa.createField(PA.X, PA.Y, optargsh=optargsh,simextent=True)
        # plot the Field object nd
        plotter.plotField(nd, name='NumberDensity')   # plot 4
        # more advanced: create a field holding the total kinetic energy on grid
        ekin = pa.createField(PA.X, PA.Y, weights=PA.Ekin_MeV, optargsh=optargsh, simextent=True)
        # The Field objectes can be used for calculations. Here we use this to
        # calculate the average kinetic energy on grid and plot
        plotter.plotField(ekin / nd, name='Avg Kin Energy (MeV)')  # plot 5

        # use optargsh to force lower resolution
        # plot number density
        plotter.plotField(pa.createField(PA.X, PA.Y, optargsh=optargsh))  # plot 6
        # plot phase space
        plotter.plotField(pa.createField(PA.X, PA.P, optargsh=optargsh))  # plot 7

        # same with high resolution
        plotter.plotField(pa.createField(PA.X, PA.Y, optargsh={'bins': [1000,1000]}))  # plot 8
        plotter.plotField(pa.createField(PA.X, PA.P, optargsh={'bins': [1000,1000]}))  # plot 9

        # advanced: postpic has already defined a lot of particle scalars as Px, Py, Pz, P, X, Y, Z, gamma, beta, Ekin, Ekin_MeV, Ekin_MeV_amu, ... but if needed you can also define your own particle scalar on the fly.
        # In case its regularly used it should be added to postpic. If you dont know how, just let us know about your own useful particle scalar by email or adding an issue at
        # https://github.com/skuschel/postpic/issues

        # define your own particle scalar: p_r = sqrt(px**2 + py**2)/p
        def p_r(pa):
            return np.sqrt(pa.Px()**2 + pa.Py()**2) / pa.P()
        # add unit and name for automatic labeling when plotted with plotField method
        p_r.unit=''
        p_r.name='$\sqrt{P_x^2 + P_y^2} / P$'
        # define another own particle scalar: r = sqrt(x**2 + y**2)
        def r(pa):
            return np.sqrt(pa.X()**2 + pa.Y()**2)
        r.unit='m'
        r.name='r'
        # use the plotter with the particle scalars defined above.
        plotter.plotField(pa.createField(r, p_r, optargsh={'bins':[400,400]}))  # plot 10


