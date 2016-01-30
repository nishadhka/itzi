#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MODULE:    t.sim.flood

AUTHOR(S): Laurent Courty

PURPOSE:   Simulate superficial water flows using a quasi-2D implementation
           of the Shallow Water Equations.
           See:
           De Almeida, G. & Bates, P., 2013. Applicability of the local
           inertial approximation of the shallow water equations to
           flood modeling. Water Resources Research, 49(8), pp.4833–4844.
           Sampson, C.C. et al., 2013. An automated routing methodology
           to enable direct rainfall in high resolution shallow water models.
           Hydrological Processes, 27(3), pp.467–476.

COPYRIGHT: (C) 2015 by Laurent Courty

            This program is free software; you can redistribute it and/or
            modify it under the terms of the GNU General Public License
            as published by the Free Software Foundation; either version 2
            of the License, or (at your option) any later version.

            This program is distributed in the hope that it will be useful,
            but WITHOUT ANY WARRANTY; without even the implied warranty of
            MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
            GNU General Public License for more details.
"""

#%module
#% description: Simulate superficial flows using simplified shallow water equations
#% keywords: raster
#% keywords: Shallow Water Equations
#% keywords: flow
#% keywords: flood
#% keywords: inundation
#%end

#%flag
#% key: p
#% description: Activate profiler
#%end

#%option G_OPT_R_ELEV
#% key: in_z
#% description: Input elevation (raster map/stds)
#% required: yes
#%end

#%option G_OPT_R_INPUT
#% key: in_n
#% description: Input friction coefficient (raster map/stds)
#% required: yes
#%end

#%option G_OPT_R_INPUT
#% key: in_h
#% description: Input starting water depth (raster map)
#% required: no
#%end

#~ #%option G_OPT_R_INPUT
#~ #% key: in_y
#~ #% description: Input starting water surface elevation (raster map)
#~ #% required: no
#~ #%end

#%option G_OPT_STRDS_INPUT
#% key: in_rain
#% description: Input rainfall (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_inf
#% description: Input infiltration rate (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_eff_por
#% description: Effective porosity (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_cap_pressure
#% description: Wetting front capillary pressure head (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_hyd_conduct
#% description: Hydraulic conductivity (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_q
#% description: Input user flow (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_bctype
#% description: Input boundary conditions type (raster map/stds)
#% required: no
#%end

#%option G_OPT_STRDS_INPUT
#% key: in_bcval
#% description: Input boundary conditions values (raster map/stds)
#% required: no
#%end


#%option G_OPT_STRDS_OUTPUT
#% key: out_h
#% description: Output water depth (strds)
#% required: no
#%end

#%option G_OPT_STRDS_OUTPUT
#% key: out_wse
#% description: Output water surface elevation (strds)
#% required: no
#%end

#~ #%option G_OPT_R_OUTPUT
#~ #% key: out_vx
#~ #% description: Output velocity strds for x direction (strds)
#~ #% required: no
#~ #%end
#~ 
#~ #%option G_OPT_R_OUTPUT
#~ #% key: out_vy
#~ #% description: Output velocity strds for y direction (strds)
#~ #% required: no
#~ #%end

#%option
#% key: hmin
#% description: Water depth threshold in metres
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: slmax
#% description: Slope threshold in m/m
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: cfl
#% description: CFL coefficient used to calculate time-step
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: theta
#% description: Flow weighting coefficient
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: vrouting
#% description: Rain routing velocity in m/s
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: dtmax
#% description: Maximum time-step in seconds
#% required: no
#% multiple: no
#% guisection: Parameters
#%end

#%option
#% key: start_time
#% description: Start of the simulation. Format yyyy-mm-dd HH:MM
#% required: no
#% multiple: no
#% guisection: Time
#%end

#%option
#% key: end_time
#% description: End of the simulation. Format yyyy-mm-dd HH:MM
#% required: no
#% multiple: no
#% guisection: Time
#%end

#%option
#% key: sim_duration
#% description: Duration of the simulation. Format HH:MM:SS
#% required: no
#% multiple: no
#% guisection: Time
#%end

#%option
#% key: record_step
#% description: Duration between two records. Format HH:MM:SS
#% required: yes
#% multiple: no
#% guisection: Time
#%end

#%option G_OPT_F_INPUT
#% key: param_file
#% required: no
#%end

#%option
#% key: stats_file
#% required: no
#% label: Output statistic file
#%end

import sys
import os
from datetime import datetime, timedelta
import numpy as np
import cProfile
import pstats
import StringIO

import grass.script as grass
from grass.pygrass.gis.region import Region
from grass.pygrass.messages import Messenger

import simulation
import gis


def main():
    # start profiler
    if flags['p']:
        pr = cProfile.Profile()
        pr.enable()

    # start messenger
    msgr = Messenger()

    # stop program if location is latlong
    if grass.locn_is_latlong():
        msgr.fatal(_("latlong location is not supported"))

    # values to be passed to simulation
    sim_param = {'hmin':0.005, 'cfl':0.7, 'theta':0.9, 'vrouting':0.1, 'dtmax':5., 'slmax':.5}
    input_times = {'start':None,'end':None,'duration':None,'rec_step':None}
    input_map_names = {'in_z': None, 'in_n': None, 'in_h': None,
        'in_rain': None, 'in_inf':None,
        'in_eff_por': None, 'in_cap_pressure': None, 'in_hyd_conduct': None,
        'in_q':None, 'in_bcval': None, 'in_bctype': None}
    output_map_names = {'out_h':None, 'out_wse':None,
        'out_vx':None, 'out_vy':None, 'out_qx':None, 'out_qy':None}

    # check and load input values
    read_input_time(msgr, options, input_times)
    read_maps_names(msgr, options, input_map_names, output_map_names)
    read_sim_param(msgr, options, sim_param)

    # Run simulation
    sim = simulation.SuperficialFlowSimulation(
                        start_time=input_times['start'],
                        end_time=input_times['end'],
                        sim_duration=input_times['duration'],
                        record_step=input_times['rec_step'],
                        stats_file = options['stats_file'],
                        dtype=np.float32,
                        input_maps=input_map_names,
                        output_maps=output_map_names,
                        sim_param=sim_param)
    sim.run()

    # end profiling
    if flags['p']:
        pr.disable()
        stat_stream = StringIO.StringIO()
        sortby = 'time'
        ps = pstats.Stats(pr, stream=stat_stream).sort_stats(sortby)
        ps.print_stats(10)
        print stat_stream.getvalue()

def file_exist(map_id):
    """Return True if name is an existing map or stds, False otherwise
    """
    if gis.Igis.name_is_map(map_id) or gis.Igis.name_is_stds(map_id):
        return True
    else:
        return False

def str_to_timedelta(inp_str):
    """Takes a string in the form HH:MM:SS
    and return a timedelta object
    """
    data = inp_str.split(":")
    hours = int(data[0])
    minutes = int(data[1])
    seconds = int(data[2])
    if hours < 0:
        raise ValueError
    if not 0 <= minutes <= 59 or not 0 <= seconds <= 59:
        raise ValueError
    obj_dt = timedelta(hours=hours,
                    minutes=minutes,
                    seconds=seconds)
    return obj_dt

def read_input_time(msgr, opts, input_times):
    """Check the sanity of input time information
    write the value to relevant dict
    """
    date_format = '%Y-%m-%d %H:%M'
    rel_err_msg = "{}: format should be HH:MM:SS"
    abs_err_msg = "{}: format should be yyyy-mm-dd HH:MM"
    comb_err_msg = ("accepted combinations:{d} alone, {s} and {d}, {s} and {e}"
                ).format(d='sim_duration', s='start_time', e='end_time')
    # record step
    try:
        input_times['rec_step'] = str_to_timedelta(opts['record_step'])
    except:
        msgr.fatal(_(rel_err_msg.format('record_step')))

    # check valid combination to get simulation duration
    b_dur = (opts['sim_duration']
                and not opts['start_time'] and not opts['end_time'])
    b_start_dur = (opts['start_time'] and opts['sim_duration']
                and not opts['end_time'])
    b_start_end = (opts['start_time'] and opts['end_time']
                and not opts['sim_duration'])
    if not (b_dur or b_start_dur or b_start_end):
        msgr.fatal(_(comb_err_msg))

    if opts['end_time']:
        try:
            input_times['end'] = datetime.strptime(opts['end_time'], date_format)
        except ValueError:
            msgr.fatal(_(abs_err_msg.format('end_time')))

    if opts['start_time']:
        try:
            input_times['start'] = datetime.strptime(opts['start_time'],
                                                    date_format)
        except ValueError:
            msgr.fatal(_(abs_err_msg.format('start_time')))
    else:
        input_times['start'] = datetime.min

    if opts['sim_duration']:
        try:
            input_times['duration'] = str_to_timedelta(opts['sim_duration'])
        except:
            msgr.fatal(_(rel_err_msg.format('sim_duration')))
    else:
        input_times['duration'] = input_times['end'] - input_times['start']

def read_maps_names(msgr, opt, input_map_names, output_map_names):
    """Read options and populate input and output name dictionaries
    """
    for k, v in opt.iteritems():
        if k in input_map_names.keys() and v:
            input_map_names[k] = v
        if k in output_map_names.keys() and v:
            if file_exist(gis.Igis.format_id(v)) and not grass.overwrite():
                msgr.fatal(_("File {} exists and will not be overwritten".format(v)))
            else:
                output_map_names[k] = v
    # check coherence of infiltration maps
    ga_list = ['in_eff_por', 'in_cap_pressure', 'in_hyd_conduct']
    for i in ga_list:
        if i in input_map_names.values():
            ga_bool = True
        else:
            ga_bool = False
    if 'in_f' in input_map_names.values() and ga_bool:
        msgr.fatal(_("Infiltration model incompatible with user-defined rate"))
    # check if all maps for Green-Ampt are presents
    if ga_bool and not all(i in input_map_names.values() for i in ga_list):
        msgr.fatal(_("{} are mutualy inclusive".format(ga_list)))

def read_sim_param(msgr, opt, sim_param):
    """Read simulation parameters and populate the corresponding dictionary
    """
    for k, v in opt.iteritems():
        if k in sim_param.keys() and v:
            sim_param[k] = float(v)


if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())
