# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2011 Nexedi SA and Contributors. All Rights Reserved.
#                    Lucas Carvalho <lucas@nexedi.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################


import transaction
from StringIO import StringIO
from Products.ERP5Type.tests.ERP5TypeTestCase import ERP5TypeTestCase
from ShaCacheMixin import ShaCacheMixin


class TestShaCache(ShaCacheMixin, ERP5TypeTestCase):
  """
    ShaCache - HTTP File Cache server
  """

  def getTitle(self):
    """
      Return the title of the current test set.
    """
    return "SHACACHE - HTTP File Cache Server"

  def beforeTearDown(self):
    """
      Clear everything for next test.
    """
    for module in ('document_module',):
      folder = self.portal[module]
      folder.manage_delObjects(list(folder.objectIds()))
    transaction.commit()
    self.tic()

  def postFile(self, key=None):
    """
      Post the file
    """
    if key is None:
      key = self.key

    try:
      data_file = StringIO()
      data_file.write(self.data)
      data_file.seek(0)

      self.portal.changeSkin('SHACACHE')
      self.shacache.REQUEST.set('method', 'POST')
      self.shacache.REQUEST.set('Content-Type', 'application/json')
      self.shacache.REQUEST._file = data_file
      self.shacache.WebSection_getDocumentValue(key)
      self.stepTic()
    finally:
      data_file.close()

  def getFile(self, key=None):
    """
      Get the file calling the Python Script.
      It simulates the real usage.
    """
    if key is None:
      key = self.key

    self.portal.changeSkin('SHACACHE')
    self.shacache.REQUEST.set('method', 'GET')
    return self.shacache.WebSection_getDocumentValue(key)

  def test_post_file(self):
    """
      Check if the posted file has all the properties defined.
    """
    self.postFile()
    self.assertEquals(1, len(self.portal.document_module))

    document = self.portal.document_module.contentValues()[0]
    self.assertEquals(self.key, document.getTitle())
    self.assertEquals(self.key, document.getReference())
    self.assertEquals(self.data, document.getData())
    self.assertEquals('application/octet-stream', document.getContentType())

  def test_get_file(self):
    """
      Check if the file returned is the correct.
    """
    self.test_post_file()
    self.assertEquals(1, len(self.portal.document_module))

    document = self.getFile()
    self.assertNotEquals(None, document)

    self.assertEquals(self.data, document.getData())
