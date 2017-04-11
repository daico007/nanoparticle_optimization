from __future__ import division
from __future__ import print_function

from copy import deepcopy

import numpy as np
from openmdao.api import Component, Group, IndepVarComp, Problem, ScipyOptimizer


class Optimization(Component):
    def __init__(self, forcefield, systems, targets, configurations=50, norm=True,
                 verbose=False):
        super(Optimization, self).__init__()

        if not hasattr(systems, "__iter__"):
            systems = [systems]
        if not hasattr(targets, "__iter__"):
            targets = [targets]
        assert len(systems) == len(targets)

        self.configurations = configurations
        self.forcefield = forcefield
        self.norm = norm
        self.systems = systems
        self.targets = targets
        self.verbose = verbose

        for parameter in forcefield.__dict__:
            if not forcefield.__dict__[parameter].fixed:
                self.add_param(parameter, val=forcefield.__dict__[parameter].value)

        self.add_output('residual', shape=1)

    def driver(self):
        top = Problem()
        root = top.root = Group()

        for i, key in enumerate(self._init_params_dict):
            root.add('p{}'.format(i), 
                IndepVarComp(key, self._init_params_dict[key]['val']))
        root.add('p', self)

        for i, key in enumerate(self._init_params_dict):
            root.connect('p{}.{}'.format(i, key), 'p.{}'.format(key))

        top.driver = ScipyOptimizer()
        top.driver.options['optimizer'] = 'COBYLA'

        for i, key in enumerate(self._init_params_dict):
            top.driver.add_desvar('p{}.{}'.format(i, key),
                lower=self.forcefield.__dict__[key].lower,
                upper=self.forcefield.__dict__[key].upper)
        top.driver.add_objective('p.residual')

        top.setup(check=True)
        top.run()

    def solve_nonlinear(self, params, unknowns, resids):
        for parameter in self._init_params_dict:
            self.forcefield.__dict__[parameter].value = params[parameter]

        residual = 0
        for system, target in zip(self.systems, self.targets):
            residual += system.calc_error(self.forcefield, target,
                configurations=self.configurations, norm=self.norm)
        
        unknowns['residual'] = residual

        if self.verbose:
            print('Current values:')
            for parameter in self._init_params_dict:
                self.forcefield.__dict__[parameter].value = params[parameter]
                print('{}:\t{}'.format(parameter, params[parameter]))
            print('Residual:\t{}\n'.format(residual))

if __name__ == "__main__":
    from nanoparticle_optimization.forcefield import Mie, Parameter
    from nanoparticle_optimization.lib.CG_nano import CG_nano
    from nanoparticle_optimization.system import System
    from nanoparticle_optimization.target import load

    sigma = Parameter(value=0.8, fixed=True)
    epsilon = Parameter(value=0.4, upper=0.6, lower=0.3)
    n = Parameter(value=12.0, upper=25.0, lower=10.0)
    m = Parameter(value=6.0, fixed=True)
    ff = Mie(sigma=sigma, epsilon=epsilon, n=n, m=m)

    nano = CG_nano(3.0, sigma=0.8)
    system = System(nano)
    target = load('/Users/asummers/Documents/Coarse-grained-nps/All-atom/U-np-np/U_3nm.txt')
    target.separations /= 10.0
    optimization = Optimization(ff, system, target, configurations=2, verbose=True)
    optimization.driver()
