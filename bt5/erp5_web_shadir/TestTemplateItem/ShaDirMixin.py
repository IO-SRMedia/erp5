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


import hashlib
import json
import platform
from DateTime import DateTime


class ShaDirMixin(object):
  """
    ShaDir - Mixin Class
  """

  def getBusinessTemplateList(self):
    """
      Return the list of required business templates.
    """
    return ('erp5_full_text_myisam_catalog',
            'erp5_base',
            'erp5_jquery',
            'erp5_ingestion_mysql_innodb_catalog',
            'erp5_ingestion',
            'erp5_web',
            'erp5_dms',
            'erp5_pdm',
            'erp5_data_set',
            'erp5_web_download_theme',
            'erp5_web_shacache',
            'erp5_web_shadir',)


  def afterSetUp(self):
    """
      Initialize the ERP5 site.
    """
    self.login()
    self.portal = self.getPortal()

    self.key = self.portal.Base_generateRandomString()
    self.file_name = 'file.txt'
    self.urlmd5 = hashlib.md5(self.key).hexdigest()
    self.file_content = 'This is the content.'
    self.file_sha512sum = hashlib.sha512(self.file_content).hexdigest()
    self.distribution = 'pypi'
    self.creation_date = DateTime()
    self.expiration_date = self.creation_date + 30

    libc_version = '%s %s' % (platform.libc_ver()[0], platform.libc_ver()[1])
    self.architecture = '%s %s' % (platform.machine(), libc_version)

    self.data_list = [{'file': self.file_name,
                      'urlmd5': self.urlmd5,
                      'sha512': self.file_sha512sum,
                      'creation_date': str(self.creation_date),
                      'expiration_date': str(self.expiration_date),
                      'distribution': self.distribution,
                      'architecture': self.architecture},
                      "User SIGNATURE goes here."]

    self.data = json.dumps(self.data_list)
    self.sha512sum = hashlib.sha512(self.data).hexdigest()

    module = self.portal.web_site_module
    shadir = getattr(module, 'shadir', None)
    if shadir is None:
      shadir = module.newContent(portal_type='Web Site',
                                 id='shadir',
                                 title='SHA Dir Server',
                                 skin_selection_name='SHADIR')


    isTransitionPossible = self.portal.portal_workflow.isTransitionPossible
    if isTransitionPossible(shadir, 'publish'):
      shadir.publish()
      self.stepTic()

    self.shadir = shadir
