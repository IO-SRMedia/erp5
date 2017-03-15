# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2017 Nexedi SARL and Contributors. All Rights Reserved.
#                    Ayush-Tiwari <ayush.tiwari@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import gc
import os
import posixpath
import transaction
import imghdr
import tarfile
import time
import hashlib
import fnmatch
import re
import threading
from copy import deepcopy
from collections import defaultdict
from cStringIO import StringIO
from OFS.Image import Pdata
from lxml.etree import parse
from urllib import quote, unquote
from OFS import SimpleItem, XMLExportImport
from datetime import datetime
from itertools import chain
from operator import attrgetter
from Products.ERP5Type.XMLObject import XMLObject
from Products.CMFCore.utils import getToolByName
from Products.PythonScripts.PythonScript import PythonScript
from Products.ERP5Type.dynamic.lazy_class import ERP5BaseBroken
from Products.ERP5Type.Globals import Persistent
from Products.ERP5Type import Permissions, PropertySheet, interfaces
from AccessControl import ClassSecurityInfo, Unauthorized, getSecurityManager
from Acquisition import Implicit, aq_base, aq_inner, aq_parent
from Products.ERP5Type.Globals import InitializeClass
from Products.ERP5Type.TransactionalVariable import getTransactionalVariable
from zLOG import LOG, INFO, WARNING
from Products.ERP5Type.patches.ppml import importXML
from Products.ERP5Type.Accessor.Constant import PropertyGetter as ConstantGetter
customImporters = {
    XMLExportImport.magic: importXML,
    }

CACHE_DATABASE_PATH = None
try:
  if int(os.getenv('ERP5_BT5_CACHE', 0)):
    from App.config import getConfiguration
    import gdbm
    instancehome = getConfiguration().instancehome
    CACHE_DATABASE_PATH = os.path.join(instancehome, 'bt5cache.db')
except TypeError:
  pass
cache_database = threading.local()
_MARKER = []

SEPARATELY_EXPORTED_PROPERTY_DICT = {
  # For objects whose class name is 'class_name', the 'property_name'
  # attribute is removed from the XML export, and the value is exported in a
  # separate file, with extension specified by 'extension'.
  # 'extension' must be None for auto-detection.
  #
  # class_name: (extension, unicode_data, property_name),
  "Document Component":  ("py",   0, "text_content"),
  "DTMLDocument":        (None,   0, "raw"),
  "DTMLMethod":          (None,   0, "raw"),
  "Extension Component": ("py",   0, "text_content"),
  "File":                (None,   0, "data"),
  "Image":               (None,   0, "data"),
  "OOoTemplate":         ("oot",  1, "_text"),
  "PDF":                 ("pdf",  0, "data"),
  "PDFForm":             ("pdf",  0, "data"),
  "Python Script":       ("py",   0, "_body"),
  "PythonScript":        ("py",   0, "_body"),
  "Spreadsheet":         (None,   0, "data"),
  "SQL":                 ("sql",  0, "src"),
  "SQL Method":          ("sql",  0, "src"),
  "Test Component":      ("py",   0, "text_content"),
  "Test Page":           (None,   0, "text_content"),
  "Web Page":            (None,   0, "text_content"),
  "Web Script":          (None,   0, "text_content"),
  "Web Style":           (None,   0, "text_content"),
  "ZopePageTemplate":    ("zpt",  1, "_text"),
}


def _delObjectWithoutHook(obj, id):
  """OFS.ObjectManager._delObject without calling manage_beforeDelete."""
  ob = obj._getOb(id)
  if obj._objects:
    obj._objects = tuple([i for i in obj._objects if i['id'] != id])
  obj._delOb(id)
  try:
    ob._v__object_deleted__ = 1
  except:
    pass


def _recursiveRemoveUid(obj):
  """Recusivly set uid to None, to prevent (un)indexing.
  This is used to prevent unindexing real objects when we delete subobjects on
  a copy of this object.
  """
  if getattr(aq_base(obj), 'uid', _MARKER) is not _MARKER:
    obj.uid = None
  for subobj in obj.objectValues():
    _recursiveRemoveUid(subobj)


class BusinessManager(XMLObject):

  """Business Manager is responsible for saving objects and properties in
  an ERP5Site. Everything will be saved just via path"""

  meta_type = 'ERP5 Business Manager'
  portal_type = 'Business Manager'
  add_permission = Permissions.AddPortalContent

  # Declarative security
  security = ClassSecurityInfo()
  security.declareObjectProtected(Permissions.AccessContentsInformation)

  _properties = (
    {'id': 'template_path_list',
     'type': 'lines',
     'default': 'python: ()',
     'acquisition_base_category': (),
     'acquisition_portal_type': (),
     'acquisition_depends': None,
     'acquisition_accessor_id': 'getTemplatePathList',
     'override': 1,
     'mode': 'w'},
     {'id': 'template_format_version',
     'type': 'int',
     'default': 'python: 3',
     'acquisition_base_category': (),
     'acquisition_portal_type': (),
     'acquisition_depends': None,
     'acquisition_accessor_id': 'getTemplateFormatVersion',
     'override': 1,
     'mode': 'w'},
     )

  template_path_list = ()
  template_format_version = 3
  status = 'uninstalled'

  # Declarative security
  security = ClassSecurityInfo()
  security.declareObjectProtected(Permissions.AccessContentsInformation)

  # Declarative properties
  property_sheets = (
                      PropertySheet.Base,
                      PropertySheet.XMLObject,
                      PropertySheet.SimpleItem,
                      PropertySheet.CategoryCore,
                      PropertySheet.Version,
                    )

  def getStatus(self):
    """
    installed       :BI(s) are installed in OFS.
    uninstalled     :Values for BI(s) at the current version removed from OFS.
    reduced         :No two BI of same path exist at different layers.
    flatenned       :BI(s) should be at the zeroth layer.
    built           :BI(s) do have values from the OS DB.
    """
    return self.status

  def setStatus(self, status=None):
    if not status:
      raise ValueError, 'No status provided'
    else:
      self.status = status

  def applytoERP5(self, DB):
    """Apply the flattened/reduced Business Manager to the DB"""
    portal = self.getPortalObject()
    pass

  def edit(self, **kw):
    """
    Explicilty edit the class instance
    XXX: No need of this class ? as we already have _edit from ERP5Type.Folder
    """
    if 'template_path_list' in kw:
      path_item_list = kw.pop('template_path_list')
      self._setTemplatePathList(path_item_list)

  def _setTemplatePathList(self, path_item_list):
    self.template_path_list = path_item_list

  def getTemplatePathList(self):
    return self.template_path_list

  security.declareProtected(Permissions.ManagePortal, '_getTemplatePathList')
  def _getTemplatePathList(self):
    result = self.getTemplatePathList()
    if not isinstance(result, tuple):
      result = tuple(result)
    return result

  def getTemplateFormatVersion(self):
    return self.template_format_version

  def _setTemplateFormatVersion(self, value):
    self.template_format_version = int(value)

  def propertyMap(self):
    prop_map = super(BusinessManager, self).propertyMap()
    final_prop_map = prop_map+self._properties
    return final_prop_map

  security.declareProtected(Permissions.ManagePortal, 'export')
  def export(self, path=None, local=0, bma=None, **kw):
    """
    Export the object

    XXX: Are we planning to use something like archive for saving the exported
    objects inside a Business Manager
    """
    if not self.getStatus() == 'built':
      raise ValueError, 'Manager not built properly'
    return self._export(path, local, bma, **kw)

  def _export(self, path=None, local=0, bma=None, **kw):

    if bma is None:
      if local:
        # we export into a folder tree
        bma = BusinessManagerFolder(path, creation=1)
      else:
        # We export bm into a tarball file
        if path is None:
          path = self.getTitle()
        bma = BusinessManagerTarball(path, creation=1)

    # export bt
    for prop in self.propertyMap():
      prop_type = prop['type']
      id = prop['id']
      if id in ('id', 'uid', 'rid', 'sid', 'id_group', 'last_id', 'revision',
                'install_object_list_list', 'id_generator', 'bm_for_diff'):
        continue
      value = self.getProperty(id)
      if not value:
        continue
      if prop_type in ('text', 'string', 'int', 'boolean'):
        bma.addObject(str(value), name=id, path='bm', ext='')
      elif prop_type in ('lines', 'tokens'):
        bma.addObject('\n'.join(value), name=id, path='bm', ext='')

    # Export each part
    for item in self._path_item_list:
        item.export(context=self, bma=bma, **kw)

    return bma.finishCreation()

  security.declareProtected(Permissions.ManagePortal, 'importFile')
  def importFile(self, path):
    """
      Import all xml files in Business Manager
    """
    bma = (BusinessManagerFolder if os.path.isdir(path) else
        BusinessManagerTarball)(path, importing=1)
    bm_item = bm()
    bma.importFiles(bm_item, parent=self)
    prop_dict = {}
    for prop in self.propertyMap():
      pid = prop['id']
      if pid != 'id':
        prop_type = prop['type']
        value = bm_item.get(pid)
        if prop_type in ('text', 'string'):
          prop_dict[pid] = value or ''
        elif prop_type in ('int', 'boolean'):
          prop_dict[pid] = value or 0
        elif prop_type in ('lines', 'tokens'):
          # XXX: Do add pid[:-5] after we switch to proper getters and setters
          prop_dict[pid] = (value or '').splitlines()
    # XXX: This is not working, needs to be fixed so as it copies all the
    # properties from BMA to the newly created Business Manager
    self._edit(**prop_dict)
    self.storeTemplateData()

    #workflow_tool = self.getPortalObject().portal_workflow
    #workflow_tool.business_package_building_workflow.notifyWorkflowMethod(
    #    self, 'edit', kw={'comment': 'Downloaded'})
    for item_object in self._path_item_list:
      item_object.importFile(bma, parent=self)

    # Set the status to uninstalled
    self.setStatus('uninstalled')

  def __add__(self, other):
    """
    Adds the Business Item objects for the given Business Manager objects
    """
    self._path_item_list.extend(other._path_item_list)
    template_path_list = list(self.template_path_list)+list(other.template_path_list)
    self.template_path_list = template_path_list
    return self

  __radd__ = __add__

  def __sub__(self, other):
    """
    Override subtract to find difference b/w the values in different cases.
    """
    # Create the sha list for all path item list available in current object
    sha_list = [item._sha for item in self._path_item_list]
    # Reverse the sign of Business Item objects for the old Business Manager
    # Trying comparing/subtracting ZODB with old installed object
    for path_item in other._path_item_list:
      if path_item._sha in sha_list:
        self._path_item_list = [item for item
                                in self._path_item_list
                                if item._sha != path_item._sha]
      else:
        path_item._sign = -1
        self._path_item_list.append(path_item)

    return self

  __rsub__ = __sub__

  security.declareProtected(Permissions.ManagePortal, 'storeTemplateData')
  def storeTemplateData(self):
    """
    Store data for objects in the ERP5
    """
    LOG('Business Manager', INFO, 'Storing Manager Data')
    self._path_item_list = []
    path_item_list = self.getTemplatePathList()
    if path_item_list:
      path_item_list = [l.split(' | ') for l in path_item_list]
    for path_item in path_item_list:
      try:
        self._path_item_list.append(BusinessItem(path_item[0], path_item[1], path_item[2]))
      except IndexError:
        pass

  def build(self, no_action=False, **kw):
    """Creates new values for business item from the values from
    OFS Database"""
    LOG('Business Manager', INFO, 'Building Business Manager')
    if not no_action:
      self.storeTemplateData()
      for path_item in self._path_item_list:
        path_item.build(self, **kw)
      self.status = 'built'
    return self

  def install(self):
    """
    Installs the Business Manager in steps:

      1. Reduction of the BT
      2. Flattenning the BT
      3. Copying the object at the path mentioned in BT
    """
    if self.status == 'uninstalled':
      self.reduceBusinessManager()
    #elif self.status == 'reduced':
    #  self.flattenBusinessManager()
    self._install()

  def _install(self):
    """
    Run installation
    """
    if self.status != 'reduced':
      self.install()
    else:
      # Invoke install on every BusinessItem object
      for path_item in self._path_item_list:
        path_item.install()

  def upgrade(self):
    """Upgrade the Business Manager"""
    pass

  def flattenBusinessManager(self):
    """
    Flattening a reduced Business Manager with two path p1 and p2 where p1 <> p2:

    flatten([(p1, s1, l1, v1), (p2, s2, l2, v2)]) = [(p1, s1, 0, v1), (p2, s2, 0, v2)]
    A reduced Business Manager BT is said to be flattened if and only if:
    flatten(BT) = BT
    """
    portal = self.getPortalObject()
    if self.getStatus() != 'reduced':
      raise ValueError, 'Please reduce the BT before flatenning'
      # XXX: Maybe call reduce function on BT by itself here rather than just
      # raising the error, because there is no other choice
    else:
      path_list = self.getTemplatePathList()
      for path_item in self._path_item_list:
        path = path_item._path
        layer = path_item._layer
        # Flatten the BusinessItem to the lowest layer ?? Why required, no change
        if layer != 0:
          path_item._layer = 0
      self.status = 'flattened'

  def reduceBusinessManager(self):
    """
    Reduction is a function that takes a Business Manager as input and returns
    a smaller Business Manager by taking out values with lower priority layers.

    After taking out BusinessItem(s) with lower priority layer, we also go
    through arithmetic in case there are multiple number of BI at the higher layer

    Two path on different layer are reduced as a single path with the highest layer:

    If l1 > l2,
    reduce([(p, s, l1, (a, b, c)), (p, s, l2, (d, e))]) = [(p, s, l1, merge(a, b, c))]

    A Business Manager BT is said to be reduced if and only if:
    reduce(BT) = BT
    """
    path_list = list(set([path_item.getBusinessPath() for path_item
                 in self._path_item_list]))

    reduced_path_item_list = []

    # We separate the path list in the ones which are repeated and the ones
    # which are unique for the installation
    seen_path_list = set()
    unique_path_list = [x for x
                        in path_list
                        if x not in seen_path_list
                        and not seen_path_list.add(x)]

    # Create an extra dict for values on path which are repeated in the path list
    seen_path_dict = {path: [] for path in seen_path_list}

    for path_item in self._path_item_list:
      if path_item._path in seen_path_list:
        # In case the path is repeated keep the path_item in a separate dict
        # for further arithmetic
        seen_path_dict[path_item._path].append(path_item)
      else:
        # If the path is unique, add them in the list of reduced Business Item
        reduced_path_item_list.append(path_item)

    # Reduce the values and get the merged result out of it
    for path, path_item_list in seen_path_dict.items():

      # Create separate list of list items with highest priority
      higest_priority_layer = max(path_item_list, key=attrgetter('_layer'))._layer
      prioritized_path_item = [path_item for path_item
                               in path_item_list
                               if path_item._layer == higest_priority_layer]

      # Separate the positive and negative sign path_item
      if len(prioritized_path_item) > 1:

        path_item_list_add = [item for item
                              in prioritized_path_item
                              if item._sign > 0]

        path_item_list_subtract = [item for item
                                   in prioritized_path_item
                                   if item._sign < 0]

        combined_added_path_item = reduce(lambda x, y: x+y, path_item_list_add)
        combined_subtracted_path_item = reduce(lambda x, y: x+y, path_item_list_subtract)

        added_value = combined_added_path_item._value
        subtracted_value = combined_subtracted_path_item._value

        if added_value != subtracted_value:
          # Append the arithmetically combined path_item objects in the final
          # reduced list after removing the intersection
          added_value, subtracted_value = \
                  self._simplifyValueIntersection(added_value, subtracted_value)

          combined_added_path_item._value = added_value
          combined_subtracted_path_item._value = subtracted_value

          # Append the path_item to the final reduced path_item_list after
          # doing required arithmetic on it. Make sure to first append
          # subtracted item because while installation, we need to first
          # uninstall the old object and then install new object at same path
          reduced_path_item_list.append(combined_subtracted_path_item)
          reduced_path_item_list.append(combined_added_path_item)

      else:
        reduced_path_item_list.append(prioritized_path_item[0])

    self._path_item_list = reduced_path_item_list
    self.setStatus('reduced')

  def _simplifyValueIntersection(self, added_value, subtracted_value):
    """
    Returns values for the Business Item having same path and layer after
    removing the intersection of the values

    Parameters:
    added_value - Value for the Business Item having sign = +1
    subtracted_value - Value for Busienss Item having sign = -1
    """
    built_in_number_type = (int, long, float, complex)
    built_in_container_type = (tuple, list, dict, set)
    built_in_type_list = built_in_number_type + built_in_container_type

    # For ERP5 objects, we should return the added and subtracted values as it is
    if type(added_value).__name__ not in built_in_type_list and \
        type(subtracted_value).__name__ not in built_in_type_list:
      return added_value, subtracted_value

    # For all the values of container type, we remove the intersection
    added_value = [x for x in added_value if x not in subtracted_value]
    subtracted_value = [x for x in subtracted_value if x not in added_value]

    return added_value, subtracted_value


class BusinessItem(Implicit, Persistent):

  """Saves the path and values for objects, properties, etc, the
    attributes for a path configuration being:

    - path  (similar to an xpath expression)
        Examples of path :
          portal_type/Person
          portal_type/Person#title
          portal_type/Person#property_sheet?ancestor=DublinCore
          portal_type/Person#property_sheet?position=2
    - sign  (+1/-1)
    - layer (0, 1, 2, 3, etc.)
    - value (a set of pickable value in python)
    - hash of the value"""

  isProperty = False

  def __init__(self, path, sign=1, layer=0, value=None, *args, **kw):
    """
    Initialize/update the attributes
    """
    self.__dict__.update(kw)
    self._path = path
    self._sign = int(sign)
    self._layer = int(layer)
    self._value = value
    if value:
      # Generate hash of from the value
      self._sha = self._generateHash()
    else:
      self._sha = ''

  def _generateHash(self):
    """
    Generate hash based on value for the object.
    Initially, for simplicity, we go on with SHA256 values only
    """
    LOG('Business Manager', INFO, 'Genrating hash')
    if not self._value:
      # Raise in case there is no value for the BusinessItem object
      raise ValueError, "Value not defined for the %s BusinessItem" % self._path
    else:
      # Expects to raise error on case the value for the object
      # is not picklable
      try:
        sha256 = hashlib.sha256(self._value).hexdigest()
      except TypeError:
        sha256 = hashlib.sha256(self._value.asXML()).hexdigest()
      self._sha = sha256

  def build(self, context, **kw):
    """
    Extract value for the given path from the OFS

    Three different situations to extract value:
    1. For paths which point directly to an object in OFS
    2. For paths which point to multiple objects inside a folder
    3. For paths which point to property of an object in OFS : In this case,
    we can have URL delimiters like ?, #, = in the path
    """
    LOG('Business Manager', INFO, 'Building Business Item')
    p = context.getPortalObject()
    path = self._path
    if '#' in str(path):
      self.isProperty = True
      relative_url, property_id = path.split('#')
      obj = p.unrestrictedTraverse(relative_url)
      property_value = obj.getProperty(property_id)
      self._value = property_value
      # Generate hash for the property value
      self._generateHash()
    else:
      try:
        for relative_url in self._resolvePath(p, [], path.split('/')):
          obj = p.unrestrictedTraverse(relative_url)
          obj = obj._getCopy(context)
          obj = obj.__of__(context)
          _recursiveRemoveUid(obj)
          self._value = obj
          # Generate hash for the erp5 object value
          self._generateHash()
      except AttributeError:
        # In case the object doesn't exist, just pass without raising error
        pass

  def applyValueToPath(self):
    """
    Apply the value to the path given.

    1. If the path doesn't exist, and its a new object, create the object.
    2. If the path doesn't exist, and its a new property, apply the property on
      the object.
    3. If the path doesn't exist, and its a new property, raise error.
    """
    pass

  def _resolvePath(self, folder, relative_url_list, id_list):
    """
    We go through 3 types of paths:

    1. General path we find in erp5 for objects
    Ex: portal_type/Person
    In this case, we import/export the object on the path

    2. Path where we consider saving sub-objects also, in that case we create
    new BusinessItem for those objects
    Ex: portal_catalog/erp5_mysql_innodb/**
    This should create BI for the catalog methods sub-objects present in the
    erp5_catalog.

    This method calls itself recursively.

    The folder is the current object which contains sub-objects.
    The list of ids are path components. If the list is empty,
    the current folder is valid.
    """
    if len(id_list) == 0:
      return ['/'.join(relative_url_list)]
    id = id_list[0]
    if re.search('[\*\?\[\]]', id) is None:
      # If the id has no meta character, do not have to check all objects.
      obj = folder._getOb(id, None)
      if obj is None:
        raise AttributeError, "Could not resolve '%s' during BusinessItem processing." % id
      return self._resolvePath(obj, relative_url_list + [id], id_list[1:])
    path_list = []
    for object_id in fnmatch.filter(folder.objectIds(), id):
      if object_id != "":
        path_list.extend(self._resolvePath(
            folder._getOb(object_id),
            relative_url_list + [object_id], id_list[1:]))
    return path_list

  def setPropertyToPath(self, path, property_name, value):
    """
    Set property for the object at given path
    """
    portal = self.getPortalObject()
    obj = portal.unrestrictedTraverse(path)
    obj.setProperty(property_name, value)

  def generateXML(self):
    """
    Generate XML for different objects/type/properties differently.
    1. Objects: Use XMLImportExport from ERP5Type
    2. For properties, first get the property type, then create XML object
    for the different property differenty(Use ObjectPropertyItem from BT5)
    3. For attributes, we can export part of the object, rather than exporting
    whole of the object
    """
    pass

  def install(self, context):
    """
    Set the value to the defined path.
    """
    # In case the path denotes property, we create separate object for
    # ObjectTemplateItem and handle the installation there.
    portal = context.getPortalObject()
    if self.isProperty:
      realtive_url, property_id = self._path.split('#')
      object_property_item = ObjectPropertyTemplateItem(id_list)
      object_property_item.install()
    else:
      path_list = self._path.split('/')
      container_path = path_list[:-1]
      object_id = path_list[-1]
      try:
        container = self.unrestrictedResolveValue(portal, container_path)
      except KeyError:
        # parent object can be set to nothing, in this case just go on
        container_url = '/'.join(container_path)
      old_obj = container._getOb(object_id, None)
      # delete the old object before installing a new object
      if old_obj:
        # XXX: In case there is an old object which has been modified from the
        # older installation, then show the conflict status.
        container._delObject(object_id)
      # If sign is +1, set the new object on the container
      if self._sign == 1:
        # install object
        obj = self._value
        obj = obj._getCopy(container)
        container._setObject(object_id, obj)
        obj = container._getOb(object_id)
        obj.isIndexable = ConstantGetter('isIndexable', value=False)
        aq_base(obj).uid = portal.portal_catalog.newUid()
        del obj.isIndexable
        if getattr(aq_base(obj), 'reindexObject', None) is not None:
          obj.reindexObject()

  def unrestrictedResolveValue(self, context=None, path='', default=_MARKER,
                               restricted=0):
    """
      Get the value without checking the security.
      This method does not acquire the parent.
    """
    if isinstance(path, basestring):
      stack = path.split('/')
    else:
      stack = list(path)
    stack.reverse()
    if stack:
      if context is None:
        portal = aq_inner(self.getPortalObject())
        container = portal
      else:
        container = context

      if restricted:
        validate = getSecurityManager().validate

      while stack:
        key = stack.pop()
        try:
          value = container[key]
        except KeyError:
          LOG('BusinessManager', WARNING,
              'Could not access object %s' % (path,))
          if default is _MARKER:
            raise
          return default

        if restricted:
          try:
            if not validate(container, container, key, value):
              raise Unauthorized('unauthorized access to element %s' % key)
          except Unauthorized:
            LOG('BusinessManager', WARNING,
                'access to %s is forbidden' % (path,))
          if default is _MARKER:
            raise
          return default

        container = value

      return value
    else:
      return context

  def __add__(self, other):
    """
    Add the values from the path when the path is same for 2 objects
    """
    if self._path != other._path:
      raise ValueError, "BusinessItem are incommensurable, have different path"
    elif self._sign != other._sign:
      raise ValueError, "BusinessItem are incommensurable, have different sign"
    else:
      self._value = self._mergeValue(value_list=[self._value, other._value])
      return self

  __radd__ = __add__

  def _mergeValue(self, value_list):
    """
    Merge value in value list

    merge(a, b, c) : A monotonic commutative function that depends on the
    type of a, b and c:

    if a, b and c are sets, merge = union
    if a, b and c are lists, merge = ordered concatenation
    if a, b and c are objects, merge = the object created the last
    else merge = MAX
    """
    builtin_number_type = (int, long, float, complex)

    # Now, consider the type of both values
    if all(isinstance(x, builtin_number_type) for x in value_list):
      merged_value = max(value_list)
    elif all(isinstance(x, set) for x in value_list):
      merged_value = set(chain.from_iterable(value_list))
    elif all(isinstance(x, list) for x in value_list):
      merged_value = list(chain.from_iterable(value_list))
    elif all(isinstance(x, tuple) for x in value_list):
      merged_value = tuple(chain.from_iterable(value_list))
    else:
      # In all other case, check if the values are objects and then take the
      # objects created last.

      # XXX: Should we go with creation date or modification_date ??
      # TODO:
      # 1. Add check that the values are ERP5 objects
      # 2. In case 2 maximum values are created at same time, prefer one with
      # higher priority layer
      merged_value = max([max(value, key=attrgetter('creation_date'))
                          for value in value_list],
                         key=attrgetter('creation_date'))

    return merged_value

  def _guessFilename(self, document, key, data):
    """
    Try to guess the extension based on the id of the document
    """
    yield key
    document_base = aq_base(document)
    # Try to guess the extension based on the reference of the document
    if hasattr(document_base, 'getReference'):
      yield document.getReference()
    elif isinstance(document_base, ERP5BaseBroken):
      yield getattr(document_base, "reference", None)
    # Try to guess the extension based on the title of the document
    yield getattr(document_base, "title", None)
    # Try to guess from content
    if data:
      for test in imghdr.tests:
        extension = test(data, None)
        if extension:
          yield 'x.' + extension

  def guessExtensionOfDocument(self, document, key, data=None):
    """
    Guesses and returns the extension of an ERP5 document.

    The process followed is:
    1. Try to guess extension by the id of the document
    2. Try to guess extension by the title of the document
    3. Try to guess extension by the reference of the document
    4. Try to guess from content (only image data is tested)

    If there's a content type, we only return an extension that matches.

    In case everything fails then:
    - '.bin' is returned for binary files
    - '.txt' is returned for text
    """
    document_base = aq_base(document)
    # XXX Zope items like DTMLMethod would not implement getContentType method
    mime = None
    if hasattr(document_base, 'getContentType'):
      content_type = document.getContentType()
    elif isinstance(document_base, ERP5BaseBroken):
      content_type = getattr(document_base, "content_type", None)
    else:
      content_type = None
    # For stable export, people must have a MimeTypes Registry, so do not
    # fallback on mimetypes. We prefer the mimetypes_registry because there
    # are more extensions and we can have preferred extensions.
    # See also https://bugs.python.org/issue1043134
    mimetypes_registry = self.getPortalObject()['mimetypes_registry']
    if content_type:
      try:
        mime = mimetypes_registry.lookup(content_type)[0]
      except (IndexError, MimeTypeException):
        pass

    for key in self._guessFilename(document, key, data):
      if key:
        ext = os.path.splitext(key)[1][1:].lower()
        if ext and (mimetypes_registry.lookupExtension(ext) is mime if mime
                    else mimetypes_registry.lookupExtension(ext)):
          return ext

    if mime:
      # return first registered extension (if any)
      if mime.extensions:
        return mime.extensions[0]
      for ext in mime.globs:
        if ext[0] == "*" and ext.count(".") == 1:
          return ext[2:].encode("utf-8")

    # in case we could not read binary flag from mimetypes_registry then return
    # '.bin' for all the Portal Types where exported_property_type is data
    # (File, Image, Spreadsheet). Otherwise, return .bin if binary was returned
    # as 1.
    binary = getattr(mime, 'binary', None)
    if binary or binary is None is not data:
      return 'bin'
    # in all other cases return .txt
    return 'txt'

  def removeProperties(self,
                       obj,
                       export,
                       properties=[],
                       keep_workflow_history=False,
                       keep_workflow_history_last_history_only=False):
    """
    Remove unneeded properties for export
    """
    obj._p_activate()
    klass = obj.__class__
    classname = klass.__name__
    attr_set = {'_dav_writelocks', '_filepath', '_owner', '_related_index',
                'last_id', 'uid',
                '__ac_local_roles__', '__ac_local_roles_group_id_dict__'}
    if properties:
      for prop in properties:
        if prop.endswith('_list'):
          prop = prop[:-5]
        attr_set.add(prop)
    if export:
      if keep_workflow_history_last_history_only:
        self._removeAllButLastWorkflowHistory(obj)
      elif not keep_workflow_history:
        attr_set.add('workflow_history')
      # PythonScript covers both Zope Python scripts
      # and ERP5 Python Scripts
      if isinstance(obj, PythonScript):
        attr_set.update(('func_code', 'func_defaults', '_code',
                         '_lazy_compilation', 'Python_magic'))
        for attr in 'errors', 'warnings', '_proxy_roles':
          if not obj.__dict__.get(attr, 1):
            delattr(obj, attr)
      elif classname in ('File', 'Image'):
        attr_set.update(('_EtagSupport__etag', 'size'))
      elif classname == 'SQL' and klass.__module__ == 'Products.ZSQLMethods.SQL':
        attr_set.update(('_arg', 'template'))
      elif interfaces.IIdGenerator.providedBy(obj):
        attr_set.update(('last_max_id_dict', 'last_id_dict'))
      elif classname == 'Types Tool' and klass.__module__ == 'erp5.portal_type':
        attr_set.add('type_provider_list')

    for attr in obj.__dict__.keys():
      if attr in attr_set or attr.startswith('_cache_cookie_'):
        delattr(obj, attr)

    if classname == 'PDFForm':
      if not obj.getProperty('business_template_include_content', 1):
        obj.deletePdfContent()
    return obj

  def export(self, context, bma, **kw):
    """
      Export the business item object : fill the BusinessManagerArchive with
      objects exported as XML, hierarchicaly organised.
    """
    if not self._value:
      return
    path = self.__class__.__name__ + '/'

    # We now will add the XML object and its sha hash while exporting the object
    # to Business Manager itself

    # Back compatibility with filesystem Documents
    key = self._path
    obj = self._value
    if isinstance(obj, str):
      if not key.startswith(path):
        key = path + key
      bma.addObject(obj, name=key, ext='.py')
    else:
      try:
        extension, unicode_data, record_id = \
          SEPARATELY_EXPORTED_PROPERTY_DICT[obj.__class__.__name__]
      except KeyError:
        pass
      else:
        while 1:  # not a loop
          obj = obj._getCopy(context)
          data = getattr(aq_base(obj), record_id, None)
          if unicode_data:
            if type(data) is not unicode:
              break
            try:
              data = data.encode(aq_base(obj).output_encoding)
            except (AttributeError, UnicodeEncodeError):
              break
          elif type(data) is not bytes:
            if not isinstance(data, Pdata):
              break
            data = bytes(data)
          try:
            # Delete this attribute from the object.
            # in case the related Portal Type does not exist, the object may be broken.
            # So we cannot delattr, but we can delete the key of its its broken state
            if isinstance(obj, ERP5BaseBroken):
              del obj.__Broken_state__[record_id]
              obj._p_changed = 1
            else:
              delattr(obj, record_id)
          except (AttributeError, KeyError):
            # property was acquired on a class,
            # do nothing, only .xml metadata will be exported
            break
          # export a separate file with the data
          if not extension:
            extension = self.guessExtensionOfDocument(obj, key, data
                                                      if record_id == 'data'
                                                      else None)
          bma.addObject(StringIO(data), key, path=path,
                        ext='._xml' if extension == 'xml' else '.' + extension)
          break
        # since we get the obj from context we should
        # again remove useless properties
        obj = self.removeProperties(obj, 1, keep_workflow_history=True)
        transaction.savepoint(optimistic=True)

      f = StringIO()
      XMLExportImport.exportXML(obj._p_jar, obj._p_oid, f)
      bma.addObject(f, key, path=path)

  def importFile(self, bma, parent, **kw):
    bma.importFiles(self, parent)

  def _importFile(self, file_name, file_obj, parent):
    obj_key, file_ext = os.path.splitext(file_name)
    # id() for installing several bt5 in the same transaction
    transactional_variable_obj_key = "%s-%s" % (id(self), obj_key)
    if file_ext != '.xml':
        # For ZODB Components: if .xml have been processed before, set the
        # source code property, otherwise store it in a transactional variable
        # so that it can be set once the .xml has been processed
        data = file_obj.read()
        try:
          obj = self._objects[obj_key]
        except KeyError:
          getTransactionalVariable()[transactional_variable_obj_key] = data
        else:
          self._restoreSeparatelyExportedProperty(obj, data)
    else:
      connection = self.getConnection(parent)
      __traceback_info__ = 'Importing %s' % file_name
      if hasattr(cache_database, 'db') and isinstance(file_obj, file):
        obj = connection.importFile(self._compileXML(file_obj))
      else:
        # FIXME: Why not use the importXML function directly? Are there any BT5s
        # with actual .zexp files on the wild?
        obj = connection.importFile(file_obj, customImporters=customImporters)
      self._value = obj

      data = getTransactionalVariable().get(transactional_variable_obj_key)
      if data is not None:
        self._restoreSeparatelyExportedProperty(obj, data)

  def _restoreSeparatelyExportedProperty(self, obj, data):
    unicode_data, property_name = SEPARATELY_EXPORTED_PROPERTY_DICT[
      obj.__class__.__name__][1:]
    if unicode_data:
      data = data.decode(obj.output_encoding)
    try:
      setattr(obj, property_name, data)
    except BrokenModified:
      obj.__Broken_state__[property_name] = data
      obj._p_changed = 1
    else:
      # Revert any work done by __setstate__.
      # XXX: This is enough for all objects we currently split in 2 files,
      #      but __setstate__ could behave badly with the missing attribute
      #      and newly added types may require more than this.
      self.removeProperties(obj, 1, keep_workflow_history=True)

  def getConnection(self, obj):
    while True:
      connection = obj._p_jar
      if connection is not None:
        return connection
      obj = obj.aq_parent

  def _compileXML(self, file):
    # This method converts XML to ZEXP. Because the conversion
    # is quite heavy, a persistent cache database is used to
    # store ZEXP, so the second run wouldn't have to re-generate
    # identical data again.
    #
    # For now, a pair of the path to an XML file and its modification time
    # are used as a unique key. In theory, a checksum of the content could
    # be used instead, and it could be more reliable, as modification time
    # might not be updated in some insane filesystems correctly. However,
    # in practice, checksums consume a lot of CPU time, so when the cache
    # does not hit, the increased overhead is significant. In addition, it
    # does rarely happen that two XML files in Business Manager contain
    # the same data, so it may not be expected to have more cache hits
    # with this approach.
    #
    # The disadvantage is that this wouldn't work with the archive format,
    # because each entry in an archive does not have a mtime in itself.
    # However, the plan is to have an archive to retain ZEXP directly
    # instead of XML, so the idea of caching would be completely useless
    # with the archive format.
    name = file.name
    mtime = os.path.getmtime(file.name)
    key = '%s:%s' % (name, mtime)

    try:
      return StringIO(cache_database.db[key])
    except:
      pass

    from Shared.DC.xml import ppml
    from OFS.XMLExportImport import start_zopedata, save_record, save_zopedata
    import xml.parsers.expat
    outfile=StringIO()
    try:
      data=file.read()
      F=ppml.xmlPickler()
      F.end_handlers['record'] = save_record
      F.end_handlers['ZopeData'] = save_zopedata
      F.start_handlers['ZopeData'] = start_zopedata
      F.binary=1
      F.file=outfile
      p=xml.parsers.expat.ParserCreate('utf-8')
      p.returns_unicode = False
      p.CharacterDataHandler=F.handle_data
      p.StartElementHandler=F.unknown_starttag
      p.EndElementHandler=F.unknown_endtag
      p.Parse(data)

      try:
        cache_database.db[key] = outfile.getvalue()
      except:
        pass

      outfile.seek(0)
      return outfile
    except:
      outfile.close()
      raise

  def getBusinessPath(self):
    return self._path

  def getBusinessPathSign(self):
    return self._sign

  def getBusinessPathLayer(self):
    return self._layer

  def getBusinessPathValue(self):
    return self._value

  def setBusinessPathValue(self, value):
    self._value = value

  def getBusinessPathSha(self):
    return self._sha

  def getParentBusinessManager(self):
    return self.aq_parent


class BusinessManagerArchive(object):
  """
    This is the base class for all Business Manager archives
  """

  def __init__(self, path, **kw):
    self.path = path

  def addObject(self, obj, name, path=None, ext='.xml'):
    if path:
      name = posixpath.join(path, name)
    # XXX required due to overuse of os.path
    name = name.replace('\\', '/').replace(':', '/')
    name = quote(name + ext)
    path = name.replace('/', os.sep)
    try:
      write = self._writeFile
    except AttributeError:
      if not isinstance(obj, str):
        obj.seek(0)
        obj = obj.read()
      self._writeString(obj, path)
    else:
      if isinstance(obj, str):
        obj = StringIO(obj)
      else:
        obj.seek(0)
      write(obj, path)

  def finishCreation(self):
    pass


class BusinessManagerFolder(BusinessManagerArchive):
  """
  Class archiving business manager into a folder tree
  """

  def _writeString(self, obj, path):
    object_path = os.path.join(self.path, path)
    path = os.path.dirname(object_path)
    os.path.exists(path) or os.makedirs(path)
    f = open(object_path, 'wb')
    try:
      f.write(obj)
    finally:
      f.close()

  def importFiles(self, item, parent):
    """
      Import file from a local folder
    """
    join = os.path.join
    item_name = item.__class__.__name__
    root = join(os.path.normpath(self.path), item_name, '')
    root_path_len = len(root)
    if CACHE_DATABASE_PATH:
      try:
        cache_database.db = gdbm.open(CACHE_DATABASE_PATH, 'cf')
      except gdbm.error:
        cache_database.db = gdbm.open(CACHE_DATABASE_PATH, 'nf')
    try:
      for root, dirs, files in os.walk(root):
        for file_name in files:
          file_name = join(root, file_name)
          with open(file_name, 'rb') as f:
            file_name = posixpath.normpath(file_name[root_path_len:])
            if '%' in file_name:
              file_name = unquote(file_name)
            elif item_name == 'bm' and file_name == 'revision':
              continue
            # self.revision.hash(item_name + '/' + file_name, f.read())
            f.seek(0)
            item._importFile(file_name, f, parent)
    finally:
      if hasattr(cache_database, 'db'):
        cache_database.db.close()
        del cache_database.db


class BusinessManagerTarball(BusinessManagerArchive):
  """
  Class archiving business manager into a tarball file
  """

  def __init__(self, path, creation=0, importing=0, **kw):
    super(BusinessManagerTarball, self).__init__(path, **kw)
    if creation:
      self.fobj = StringIO()
      self.tar = tarfile.open('', 'w:gz', self.fobj)
      self.time = time.time()
    elif importing:
      self.tar = tarfile.open(path, 'r:gz')
      self.item_dict = item_dict = defaultdict(list)
      for info in self.tar.getmembers():
        if info.isreg():
          path = info.name.split('/')
          if path[0] == '.':
            del path[0]
          item_dict[path[1]].append(('/'.join(path[2:]), info))

  def _writeFile(self, obj, path):
    if self.path:
      path = posixpath.join(self.path, path)
    info = tarfile.TarInfo(path)
    info.mtime = self.time
    obj.seek(0, 2)
    info.size = obj.tell()
    obj.seek(0)
    self.tar.addfile(info, obj)

  def finishCreation(self):
    self.tar.close()
    return self.fobj

  def importFiles(self, item, parent):
    """
      Import all file from the archive to the site
    """
    extractfile = self.tar.extractfile
    item_name = item.__class__.__name__
    for file_name, info in self.item_dict.get(item_name, ()):
      if '%' in file_name:
        file_name = unquote(file_name)
      elif item_name == 'bm' and file_name == 'revision':
        continue
      f = extractfile(info)
      self.revision.hash(item_name + '/' + file_name, f.read())
      f.seek(0)
      item._importFile(file_name, f, parent)


class bm(dict):
  """
  Fake 'bm' item to read bm/* files through BusinessManagerArchive
  """

  def _importFile(self, file_name, file, parent):
    self[file_name] = file.read()

#InitializeClass(BusinessManager)