#!/usr/bin/env python
#-*- coding:utf8 -*-

# This file is part of pyre-todo.
# 
# Foobar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Foobar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Foobar.  If not, see <http://www.gnu.org/licenses/>
                                        
# Simple redis-based todo list application

import sys
import os
import redis
import random
import md5
from bottle import \
        jinja2_view as view, \
        jinja2_template as template
from bottle import\
        run, \
        debug, \
        request, \
        static_file, \
        get, \
        post, \
        redirect, \
        HTTPError

# try to import settings

# sys.path = ['/home/matael/workspace/projects/pyre-todo/'] + sys.path
# os.chdir(os.path.dirname(__file__))

try:
    from settings import *
except ImportError:
    print("Unable to load settings.\nWill use default seetings...")
    REDIS_HOST ="localhost"
    REDIS_PORT = 6379
    REDIS_DB = 0
    REDIS_PREFIX = "pyre:"
    STATIC_ROOT = "./static"
    TEMPLATE_PATH = "./templates"

#### Tool functions ####

def _init_conn():
    """ Initialize a connection to the DB """
    try:
        return redis.Redis(db=REDIS_DB, host=REDIS_HOST, port=REDIS_PORT)
    except:
        return HTTPError(500)

def _pre(val):
    return "{0}{1}".format(REDIS_PREFIX, val)

#### Generic Views ####

@get('/static/<filename:path>')
def send_static(filename):
    return static_file(filename, root=STATIC_ROOT)

#### App Views ####

##### Home [/]
@get('/')
def home():
    r = _init_conn()
    len = int(r.llen(_pre("queues")))
    if len:
        queues = [r.hgetall(_pre("queues_prop:{}".format(q))) for q in r.lrange(_pre("queues"), 0, len)]
    else:
        queues = []
    return template(os.path.join(TEMPLATE_PATH, "home.html"), queues=queues)


##### Show :queue [/<queue:int>]
@get('/<queue:int>')
def show_queue(queue):
    r = _init_conn()
    if not r.exists(_pre("queues_prop:{}".format(queue))):
        return HTTPError(404, "The requested queue does not exists")
    else:
        items = [r.hgetall(_pre("items:{}".format(i))) for i in r.lrange(_pre("queues:{}".format(queue)), 0, int(r.llen(_pre("queues:{}".format(queue))))-1)]
        queue_object = r.hgetall(_pre("queues_prop:{}".format(queue)))
        return template(os.path.join(TEMPLATE_PATH, "show_queue.html"), items=items, queue=queue_object)


##### Add queue [/add]
@get('/add')
@post('/add')
def add_queue():
    if not request.POST:
        return template(os.path.join(TEMPLATE_PATH, "add.html"))
    else:
        if request.POST.get("name"):
            r = _init_conn()

            # get id for the new queue
            id = r.incr(_pre("id:q")) - 1

            # append the new queue to the list
            r.rpush(_pre("queues"), id)

            # create the properties hash
            r.hmset(
                _pre("queues_prop:{}".format(id)),
                {
                    "id":id,
                    "name":request.POST.get("name")
                }
            )

            redirect("/{}".format(id))

        else: redirect("/")


##### Delete :queue [/del/<queue:int>]
@get('/del/<queue:int>')
def delete_queue(queue):
    r = _init_conn()
    if not r.exists(_pre("queues_prop:{}".format(queue))):
        return HTTPError(404, "The requested queue does not exists")
    else:
        confirm = md5.md5(str(random.randrange(0.00000,1.00000)*100000)).hexdigest()
        # set the key in delete: with a 1 minute-delayed expiration
        r.setex(
            _pre("delete:{}".format(queue)),
            confirm, 60
        )
        queue_object = r.hgetall(_pre("queues_prop:{}".format(queue)))
        return template(os.path.join(TEMPLATE_PATH,"confirm.html"), queue=queue_object, confirm=confirm)


##### Confirm deletion [/del/confirm/:queue]
@get('/del/confirm/<queue:int>')
@post('/del/confirm/<queue:int>')
def confirm_deletion(queue):
    r = _init_conn()
    if not r.exists(_pre("queues_prop:{}".format(queue))):
        return HTTPError(404, "The requested queue does not exists")
    else:
        if not r.exists(_pre("delete:{}".format(queue))):
            redirect("/del/{}".format(queue))
        
        # we now know that <queue> exists and is flagged for deletion
        if not request.POST:
            redirect("/del/{}".format(queue))
        else:
            if request.POST.get("confirm") == r.get(_pre("delete:{}".format(queue))):
                # delete the queue
                len = r.llen(_pre("queues:{}".format(queue)))
                if len:
                    range = r.lrange(_pre("queues:{}".format(queue)), 0, len)
                    for item in range:
                        r.delete(_pre("items:{}".format(item)))
                p = r.pipeline()
                p.delete(_pre("queues:{}".format(queue)))
                p.delete(_pre("queues_prop:{}".format(queue)))
                p.lrem(_pre("queues"), 1, str(queue))
                p.execute()
                redirect("/")



##### Add item to :queue [/<queue:int>/add]
@get('/<queue:int>/add')
@post('/<queue:int>/add')
def add_item(queue):
    r = _init_conn()
    if not r.exists(_pre("queues_prop:{}".format(queue))):
        return HTTPError(404, "The requested queue does not exists")
    else:
        if not request.POST:
            queue_object = r.hgetall(_pre("queues_prop:{}".format(queue)))
            return template(os.path.join(TEMPLATE_PATH, "add_item.html"), queue=queue_object)
        else:
            if request.POST.get("name"):
                item_prop = {
                    "name": request.POST.get("name"),
                }
                if request.POST.get("description"):
                    item_prop["description"] = request.POST.get("description")
                else:
                    item_prop["description"] = ""
                
                id = r.incr(_pre("id:i"))-1
                item_prop['id'] = id
                r.hmset(
                    # create a new hash object a get the right id
                    _pre("items:{}".format(id)),
                    item_prop # fill the hash with POST data
                )
                r.rpush(
                    _pre("queues:{}".format(queue)),
                    id
                )
                # delete the queue
                redirect("/{}".format(queue))


##### Delete :item from :queue [/<queue:int>/del/<item:int>]
@get('/<queue:int>/del/<item:int>')
def delete_item(queue, item):
    r = _init_conn()
    if not r.exists(_pre("queues_prop:{}".format(queue))):
        return HTTPError(404, "The requested queue does not exists")
    else:
        if not r.exists(_pre("items:{}".format(item))):
            return HTTPError(404, "The requested item does not exists")
        else:
            r.delete(_pre("items:{}".format(item)))
            r.lrem(
                _pre("queues:{}".format(queue)),
                1,
                item
            )
            redirect("/{}".format(queue))


########## LOCAL RUN AND DEBUG #############

debug(True)
run(reloader=True)
