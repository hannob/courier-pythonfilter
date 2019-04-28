#!/usr/bin/python3

from distutils.core import setup

setup(name="courier-pythonfilter",
      version="3.0",
      description="Python filtering architecture for the Courier MTA.",
      author="Gordon Messmer",
      author_email="gordon@dragonsdawn.net",
      url="http://www.dragonsdawn.net/~gordon/courier-pythonfilter/",
      license="GPL",
      scripts=['pythonfilter', 'pythonfilter-quarantine', 'dropmsg'],
      packages=['courier', 'pythonfilter'],
      package_dir={'pythonfilter': 'filters/pythonfilter'},
      data_files=[('/etc/', ['pythonfilter.conf',
                             'pythonfilter-modules.conf'])]
     )
