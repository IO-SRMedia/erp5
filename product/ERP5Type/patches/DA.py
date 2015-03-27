##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
# Copyright (c) 2002,2005 Nexedi SARL and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

# XML content of zsql methods
import re
try: from IOBTree import Bucket
except: Bucket=lambda:{}
from Shared.DC.ZRDB.Aqueduct import decodestring, parse
from Shared.DC.ZRDB.DA import DA, DatabaseError, SQLMethodTracebackSupplement
from Shared.DC.ZRDB import RDB
from Shared.DC.ZRDB.Results import Results
from App.Extensions import getBrain
from AccessControl import getSecurityManager
from Acquisition import aq_base, aq_parent
from zLOG import LOG, INFO, ERROR
from string import find
from cStringIO import StringIO
import sys

def DA_fromFile(self, filename):
  """
    Read the file and update self
  """
  f = file(filename)
  s = f.read()
  f.close()
  self.fromText(s)

def DA_fromText(self, text):
  """
    Read the string 'text' and updates self
  """
  start = text.find('<dtml-comment>')
  end = text.find('</dtml-comment>')
  block = text[start+14:end]
  parameters = {}
  for line in block.split('\n'):
    pair = line.split(':',1)
    if len(pair)!=2:
      continue
    parameters[pair[0].strip().lower()]=pair[1].strip()
  # check for required and optional parameters
  max_rows = parameters.get('max_rows',1000)
  max_cache = parameters.get('max_cache',100)
  cache_time = parameters.get('cache_time',0)
  class_name = parameters.get('class_name','')
  class_file = parameters.get('class_file','')
  title = parameters.get('title','')
  connection_id = parameters.get('connection_id','')
  arguments = parameters.get('arguments','')
  start = text.rfind('<params>')
  end = text.rfind('</params>')
  arguments = text[start+8:end]
  template = text[end+9:]
  while template.find('\n')==0:
    template=template.replace('\n','',1)
  self.manage_edit(title=title, connection_id=connection_id,
                  arguments=arguments, template=template)
  self.manage_advanced(max_rows, max_cache, cache_time, class_name, class_file)

def DA_manage_FTPget(self):
    """Get source for FTP download"""
    self.REQUEST.RESPONSE.setHeader('Content-Type', 'text/plain')
    return """<dtml-comment>
title:%s
connection_id:%s
max_rows:%s
max_cache:%s
cache_time:%s
class_name:%s
class_file:%s
</dtml-comment>
<params>%s</params>
%s""" % (self.title, self.connection_id,
         self.max_rows_, self.max_cache_, self.cache_time_,
         self.class_name_, self.class_file_,
         self.arguments_src, self.src)

# This function doesn't take care about properties by default
def DA_PUT(self, REQUEST, RESPONSE):
    """Handle put requests"""
    if RESPONSE is not None: self.dav__init(REQUEST, RESPONSE)
    if RESPONSE is not None: self.dav__simpleifhandler(REQUEST, RESPONSE, refresh=1)
    body = REQUEST.get('BODY', '')
    m = re.match('\s*<dtml-comment>(.*?)</dtml-comment>\s*\n', body, re.I | re.S)
    if m:
        property_src = m.group(1)
        parameters = {}
        for line in property_src.split('\n'):
          pair = line.split(':',1)
          if len(pair)!=2:
            continue
          parameters[pair[0].strip().lower()]=pair[1].strip()
        # check for required and optional parameters
        max_rows = parameters.get('max_rows',1000)
        max_cache = parameters.get('max_cache',100)
        cache_time = parameters.get('cache_time',0)
        class_name = parameters.get('class_name','')
        class_file = parameters.get('class_file','')
        title = parameters.get('title','')
        connection_id = parameters.get('connection_id','')
        self.manage_advanced(max_rows, max_cache, cache_time, class_name, class_file)
        self.title = str(title)
        self.connection_id = str(connection_id)
        body = body[m.end():]
    m = re.match('\s*<params>(.*)</params>\s*\n', body, re.I | re.S)
    if m:
        self.arguments_src = m.group(1)
        self._arg=parse(self.arguments_src)
        body = body[m.end():]
    template = body
    self.src = template
    self.template=t=self.template_class(template)
    t.cook()
    self._v_cache={}, Bucket()
    if RESPONSE is not None: RESPONSE.setStatus(204)
    return RESPONSE


def DA__call__(self, REQUEST=None, __ick__=None, src__=0, test__=0, **kw):
    """Call the database method

    The arguments to the method should be passed via keyword
    arguments, or in a single mapping object. If no arguments are
    given, and if the method was invoked through the Web, then the
    method will try to acquire and use the Web REQUEST object as
    the argument mapping.

    The returned value is a sequence of record objects.
    """
    __traceback_supplement__ = (SQLMethodTracebackSupplement, self)

    c = kw.pop("connection_id", None)
    #if c is not None:
      #LOG("DA", 300, "connection %s provided to %s" %(c, self.id))
    # patch: dynamic brain configuration
    zsql_brain = kw.pop('zsql_brain', None)
    # patch end


    if REQUEST is None:
        if kw: REQUEST=kw
        else:
            if hasattr(self, 'REQUEST'): REQUEST=self.REQUEST
            else: REQUEST={}

    # Patch to implement dynamic connection id
    # Connection id is retrieve from user preference
    if c is None:
      physical_path = self.getPhysicalPath()
      # XXX cleaner solution will be needed
      if 'portal_catalog' not in physical_path and\
         'cmf_activity' not in self.connection_id and\
         'transactionless' not in self.connection_id:
        try:
          archive_id = self.portal_preferences.getPreferredArchive()
        except AttributeError:
          pass
        else:
          if archive_id not in (None, ''):
            archive_id = archive_id.split('/')[-1]
            #LOG("DA__call__, archive_id 2", 300, archive_id)
            archive = self.portal_archives._getOb(archive_id, None)
            if archive is not None:
              c = archive.getConnectionId()
              #LOG("DA call", INFO, "retrieved connection %s from preference" %(c,))

    if c is None:
      # connection hook
      c = self.connection_id
      # for backwards compatability
      hk = self.connection_hook
      # go get the connection hook and call it
      if hk: c = getattr(self, hk)()
    #LOG("DA__call__ connection", 300, c)
    try: dbc=getattr(self, c)
    except AttributeError:
        raise AttributeError, (
            "The database connection <em>%s</em> cannot be found." % (
            c))

    try: DB__=dbc()
    except: raise DatabaseError, (
        '%s is not connected to a database' % self.id)

    p = aq_parent(self) # None if no aq_parent

    argdata=self._argdata(REQUEST)
    argdata['sql_delimiter']='\0'
    argdata['sql_quote__']=dbc.sql_quote__

    security=getSecurityManager()
    security.addContext(self)
    try:
        try:     query=apply(self.template, (p,), argdata)
        except TypeError, msg:
            msg = str(msg)
            if find(msg,'client') >= 0:
                raise NameError("'client' may not be used as an " +
                    "argument name in this context")
            else: raise
    finally: security.removeContext(self)

    if src__: return query

    if self.cache_time_ > 0 and self.max_cache_ > 0:
        result=self._cached_result(DB__, query, self.max_rows_, c)
    else:
      try:
#         if 'portal_ids' in query:
#           LOG("DA query", INFO, "query = %s" %(query,))
        result=DB__.query(query, self.max_rows_)
      except:
        LOG("DA call raise", ERROR, "DB = %s, c = %s, query = %s" %(DB__, c, query), error=sys.exc_info())
        raise

    # patch: dynamic brain configuration
    if zsql_brain is not None:
        try:
          class_file_, class_name_ = zsql_brain.rsplit('.', 1)
        except:
          #import pdb; pdb.post_mortem()
          raise
        brain = getBrain(class_file_, class_name_)
        # XXX remove this logging for performance
        LOG(__name__, INFO, "Using special brain: %r\n" % (brain,))
    else:
        brain = getBrain(self.class_file_, self.class_name_)

    if type(result) is type(''):
        f=StringIO()
        f.write(result)
        f.seek(0)
        result=RDB.File(f,brain,p)
    else:
        result=Results(result, brain, p)
    columns=result._searchable_result_columns()
    if test__ and columns != self._col: self._col=columns

    # If run in test mode, return both the query and results so
    # that the template doesn't have to be rendered twice!
    if test__: return query, result

    return result

def _getTableSchema(query, name,
        create_lstrip = re.compile(r"[^(]+\(\s*").sub,
        create_rmatch = re.compile(r"(.*\S)\s*\)[^)]+\s"
          "(DEFAULT(\s+(CHARSET|COLLATE)=\S+)+).*$", re.DOTALL).match,
        create_split  = re.compile(r",\n\s*").split,
        column_match  = re.compile(r"`(\w+)`\s+(.+)").match,
        ):
    (_, schema), = query("SHOW CREATE TABLE " + name)[1]
    column_list = []
    key_set = set()
    m = create_rmatch(create_lstrip("", schema, 1))
    for spec in create_split(m.group(1)):
        if "KEY" in spec:
            key_set.add(spec)
        else:
            column_list.append(column_match(spec).groups())
    return column_list, key_set, m.group(2)

_create_search = re.compile(r'\bCREATE\s+TABLE\s+(`?)(\w+)\1\s+', re.I).search
_key_search = re.compile(r'\bKEY\s+(`[^`]+`)\s+(.+)').search

def DA_upgradeSchema(self, connection_id=None, added_list=None,
                           modified_list=None, src__=0, **kw):
    query = self.getPortalObject()[connection_id or self.connection_id]().query
    src = self(src__=1, **kw)
    m = _create_search(src)
    if m is None:
        return
    name = m.group(2)

    old_list, old_set, old_default = _getTableSchema(query, name)

    name_new = '_%s_new' % name
    query('CREATE TEMPORARY TABLE %s %s' % (name_new, src[m.end():]))
    try:
        new_list, new_set, new_default = _getTableSchema(query, name_new)
    finally:
        query("DROP TEMPORARY TABLE " + name_new)

    src = []
    q = src.append
    if old_default != new_default:
      q(new_default)

    old_dict = {}
    new = {column[0] for column in new_list}
    pos = 0
    for column, spec in old_list:
      if column in new:
          old_dict[column] = pos, spec
          pos += 1
      else:
          q("DROP COLUMN " + column)

    for key in old_set - new_set:
      if "PRIMARY" in key:
          q("DROP PRIMARY KEY")
      else:
          q("DROP KEY " + _key_search(key).group(1))

    added = str if added_list is None else added_list.append
    modified = str if modified_list is None else modified_list.append
    pos = 0
    where = "FIRST"
    for column, spec in new_list:
        try:
            old = old_dict[column]
        except KeyError:
            q("ADD COLUMN %s %s %s" % (column, spec, where))
            added(column)
        else:
            if old != (pos, spec):
                q("MODIFY COLUMN %s %s %s" % (column, spec, where))
                if old[1] != spec:
                    modified(column)
            pos += 1
        where = "AFTER " + column

    for key in new_set - old_set:
        q("ADD " + key)

    if src:
        src = "ALTER TABLE %s%s" % (name, ','.join("\n  " + q for q in src))
        if not src__:
            query(src)
        return src

DA.__call__ = DA__call__
DA.fromFile = DA_fromFile
DA.fromText = DA_fromText
DA.manage_FTPget = DA_manage_FTPget
DA.PUT = DA_PUT
DA._upgradeSchema = DA_upgradeSchema


# Patch to allow using ZODB components for brains
def getObjectMeta(original_function):
  def getObject(module, name, reload=0):
    # Modified version that ignore errors as long as the module can be be
    # imported, which is enough to use a ZODB Extension as a brain.
    try:
      m = __import__('erp5.component.extension.%s' % module, globals(),
                     {}, 'erp5.component.extension')

      o = getattr(m, name, None)
      if o is None:
        raise ImportError(
          "Cannot get %s from erp5.component.extension.%s" % (name, module))

      return o
    except ImportError:
      return original_function(module, name, reload=reload)

  return getObject

# This get Object exists both in App.Extensions.getObject and Shared.DC.ZRDB.DA
# for some versions of Zope/Products.ZSQLMethods, so we try to patch both if
# they exist
import Shared.DC.ZRDB.DA
if hasattr(Shared.DC.ZRDB.DA, 'getObject'):
  Shared.DC.ZRDB.DA.getObject = getObjectMeta(Shared.DC.ZRDB.DA.getObject)

import App.Extensions
App.Extensions.getObject = getObjectMeta(App.Extensions.getObject)
