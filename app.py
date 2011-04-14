#!/usr/bin/env python
# -*- coding: utf-8 -*-
from wsgiref.handlers import CGIHandler
from application import app

CGIHandler().run(app)
