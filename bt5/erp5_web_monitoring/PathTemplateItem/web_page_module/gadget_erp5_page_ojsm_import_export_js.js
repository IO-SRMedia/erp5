/*global window, rJS, RSVP, jsen, Rusha, Handlebars, atob */
/*jslint nomen: true, indent: 2, maxerr: 3*/
(function (window, rJS, RSVP, jsen, Rusha, Handlebars, atob) {
  "use strict";

  var gadget_klass = rJS(window),
    templater = gadget_klass.__template_element,
    notify_msg_template = Handlebars.compile(
      templater.getElementById("template-message-error").innerHTML
    ),
    storage_selection = Handlebars.compile(
      templater.getElementById("storage-selection").innerHTML
    ),
    header_title = Handlebars.compile(
      templater.getElementById("template-section-title").innerHTML
    ); 

  function getMonitorSetting(gadget) {
    return gadget.jio_allDocs({
      select_list: ["basic_login", "url", "title", "active"],
      query: '(portal_type:"opml")'
    })
    .push(function (opml_result) {
      var i,
        opml_dict = {opml_description_list: []};
      for (i = 0; i < opml_result.data.total_rows; i+= 1) {
        opml_dict.opml_description_list.push(opml_result.data.rows[i].value);
      }
      return opml_dict;
    });
  }

  function validateJsonConfiguration(json_value, uses_old_schema) {
    var validate,
      json_schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type" : "object",
        "properties": {
          "opml_description_list": {
            "description": "list of monitor opml URL",
            "type": "array",
            "required": ['basic_login', "url", "title"],
            "items": {
              "type": "object",
              "properties": {
                "url": {
                  "description": "OPML URL",
                  "type": "string"
                },
                "title": {
                  "description": "OPML title",
                  "type": "string"
                },
                "basic_login": {
                  "description": "credentials hash string",
                  "type": "string"
                },
                "active": {
                  "description": "OPML active state",
                  "type": "boolean",
                  "default": true
                }
              },
              "additionalProperties": false
            }
          }
        },
        "additionalProperties": false
      },
      old_json_schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type" : "object",
        "properties": {
          "opml_description": {
            "description": "list of monitor opml URL",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "href": {
                  "description": "OPML URL",
                  "type": "string"
                },
                "title": {
                  "description": "OPML title",
                  "type": "string"
                }
              },
              "additionalProperties": false
            }
          },
          "monitor_url": {
            "description": "list of registered monitor instance URL",
            "type": "array",
            "required": ['hash', "url", "parent_url"],
            "items": {
              "type": "object",
              "properties": {
                "hash": {
                  "description": "hash string",
                  "type": "string"
                },
                "login": {
                  "description": "login",
                  "type": "string",
                  "default": ""
                },
                "url": {
                  "description": "url of monitor instance",
                  "type": "string"
                },
                "parent_url": {
                  "description": "URL to parent instance",
                  "type": "string"
                }
              },
              "additionalProperties": false
            }
          }
        },
  
        "additionalProperties": false
      };

    return new RSVP.Queue()
      .push(function () {
        if (uses_old_schema !== undefined && uses_old_schema === true) {
          validate = jsen(old_json_schema);
        } else {
          validate = jsen(json_schema);
        }
        return validate(json_value);
      });
  }

  function importMonitorConfiguration(gadget, config) {
    var is_old_schema = false;
    gadget.state.message.textContent = "";
    return new RSVP.Queue()
      .push(function (form_doc) {
        var configuration_dict;
        if (typeof config === 'string') {
          try {
            configuration_dict = JSON.parse(config);
          } catch (e) {
            gadget.state.message
              .innerHTML = notify_msg_template({
                status: 'error',
                message: 'Error: Invalid json content!'
              });
            return;
          }
        } else {
          configuration_dict = config;
        }
        return validateJsonConfiguration(configuration_dict)
          .push(function (validate_result) {
            if (!validate_result) {
              // try validation on old setting format
              is_old_schema = true;
              return validateJsonConfiguration(configuration_dict, true);
            }
            return validate_result;
          })
          .push(function (validate_result) {
            var settings_queue = new RSVP.Queue(),
              not_imported = "",
              item,
              cred_list,
              i,
              j;

            function pushSetting(id, config) {
              settings_queue
                .push(function () {
                  return gadget.jio_put(id, config);
                })
                .push(undefined, function (error) {
                  throw error;
                });
            }
            if (validate_result) {
              if (is_old_schema) {
                //return settings_queue;
                for (i = 0; i < configuration_dict.opml_description.length; i += 1) {
                  item = {
                    title: configuration_dict.opml_description[i].title,
                    url: configuration_dict.opml_description[i].href,
                    active: true,
                    portal_type: "opml"
                  };
                  for (j = 0; j < configuration_dict.monitor_url.length; j += 1) {
                    if (configuration_dict.monitor_url[j].parent_url ===
                        configuration_dict.opml_description[i].href) {
                      item.basic_login = configuration_dict.monitor_url[j].hash;
                      cred_list = atob(item.basic_login).split(':');
                      item.username = cred_list[0];
                      item.password = cred_list[1];
                      // XXX - all monitors password in opml should be the same
                      break;
                    }
                  }
                  if (item.basic_login !== undefined) {
                    pushSetting(item.url, item);
                  } else {
                    not_imported += "OPML [" + configuration_dict.opml_description[i].title +
                      "] was not imported, bad configuration...<br/>";
                  }
                }
              } else {
                for (i = 0; i < configuration_dict.opml_description_list.length; i += 1) {
                  item = configuration_dict.opml_description_list[i];
                  item.portal_type = "opml";
                  cred_list = atob(item.basic_login).split(':');
                  item.username = cred_list[0];
                  item.password = cred_list[1];
                  pushSetting(item.url, item);
                }
              }
              return settings_queue
                .push(function () {
                  if (not_imported !== "") {
                    gadget.state.message
                      .innerHTML = notify_msg_template({
                        status: 'error',
                        message: not_imported
                      });
                    return false;
                  }
                  return true;
                });
            } else {
              gadget.state.message
                .innerHTML = notify_msg_template({
                  status: 'error',
                  message: 'Error: Content is not a valid Monitoring Json configuration!'
                });
              return false;
            }
          })
          .push(function (status) {
            if (status) {
              return gadget.redirect({
                "command": "display",
                "options": {"page": "settings_configurator"}
              });
            }
          });
      });
  }

  gadget_klass
    /////////////////////////////
    // state
    /////////////////////////////
    .setState({
      message: "",
      config: "",
      is_export: false,
      options: "",
      erp5_gadget: ""
    })
    .ready(function (g) {
      return g.getDeclaredGadget('erp5_gadget')
        .push(function (erp5_gadget) {
          return g.changeState({erp5_gadget: erp5_gadget});
        });
    })
    /////////////////////////////////////////////////////////////////
    // Acquired methods
    /////////////////////////////////////////////////////////////////
    .declareAcquiredMethod("updateHeader", "updateHeader")
    .declareAcquiredMethod("getSetting", "getSetting")
    .declareAcquiredMethod("setSetting", "setSetting")
    .declareAcquiredMethod("getUrlFor", "getUrlFor")
    .declareAcquiredMethod("redirect", "redirect")
    .declareAcquiredMethod("jio_allDocs", "jio_allDocs")
    .declareAcquiredMethod("jio_put", "jio_put")

    /////////////////////////////////////////////////////////////////
    // declared methods
    /////////////////////////////////////////////////////////////////
    .onEvent('submit', function () {
      var gadget = this;
      return gadget.getDeclaredGadget('form_view')
        .push(function (form_gadget) {
          return form_gadget.getContent();
        })
        .push(function (form_doc) {
          return importMonitorConfiguration(gadget, form_doc.config);
        });
    })

    .declareMethod("triggerSubmit", function () {
      return this.element.querySelector('button[type="submit"]').click();
    })

    .declareMethod("render", function (options) {
      var gadget = this,
        is_exporter = options.exporter === "true",
        message_element = gadget.element.querySelector('.ui-message-alert');
      message_element.textContent = "";
      if (options.url && !options.url.endsWith('/')) {
        options.url += '/';
      }
      if (is_exporter) {
        return new RSVP.Queue()
          .push(function () {
            return getMonitorSetting(gadget);
          })
          .push(function (configuration_dict) {
            return gadget.changeState({
              options: options,
              is_exporter: is_exporter,
              config: JSON.stringify(configuration_dict),
              message: message_element,
              sync: undefined
            });
          });
      }

      return gadget.changeState({
        options: options,
        is_exporter: is_exporter,
        config: "",
        message: message_element,
        sync: options.auto_sync,
        storage_url: options.url
      });
    })
    .onStateChange(function () {
      var gadget = this;
      if (gadget.state.options === "") {
        return;
      }
      return RSVP.Queue()
        .push(function () {
          var title_content;

          if (gadget.state.is_exporter) {
            title_content = header_title({
              title: "Export Monitor Configurations",
              icon: "download"
            });
          } else {
            title_content = header_title({
              title: "Import Monitor Configurations",
              icon: "upload"
            });
          }
          gadget.element.querySelector(".document-access h3").innerHTML = title_content;
          return gadget.getDeclaredGadget('form_view');
        })
        .push(function (form_view) {
          return form_view.render({
            erp5_document: {
              "_embedded": {"_view": {
                "my_config": {
                  "description": "Monitoring Settings Content (json format)",
                  "title": "Settings Content (JSON)",
                  "default": gadget.state.config || "",
                  "css_class": "",
                  "required": 1,
                  "editable": 1,
                  "key": "config",
                  "hidden": 0,
                  "type": "TextAreaField"
                }
              }},
              "_links": {
                "type": {
                  // form_list display portal_type in header
                  name: ""
                }
              }
            },
            form_definition: {
              group_list: [[
                "left",
                [["my_config"]]
              ]]
            }
          });
        })
        .push(function () {
          var new_options = JSON.parse(JSON.stringify(gadget.state.options));
          new_options.exporter = !gadget.state.is_exporter;
          new_options.auto_sync = undefined;
          new_options.url = undefined;
          return RSVP.all([
            gadget.getUrlFor({command: "display", options: new_options}),
            gadget.state.is_exporter
          ]);
        })
        .push(function (result) {
          var parameters = {
              page_title: "Monitoring Import-Export",
              export_url: result[1] ? undefined : result[0],
              import_url: result[1] ? result[0] : undefined
            };
          if (!result[1]) {
            parameters.submit_action = true;
            parameters.panel_action = false;
          }
          return gadget.updateHeader(parameters);
        })
        .push(function () {
          var div = gadget.element.querySelector('.storage-list');
          if (gadget.state.is_exporter) {
            while (div.firstChild) {
              div.removeChild(div.firstChild);
            }
            return;
          }
          return gadget.getUrlFor({command: "display", options: {page: "ojsm_erp5_configurator", type: "erp5"}})
            .push(function (url) {
              gadget.element.querySelector('.storage-list').innerHTML = storage_selection({
                documentlist: [{
                  "link": url,
                  "title": "SlapOS Master ERP5"
                }]
              });
            });
        })
        .push(function () {
          if (gadget.state.sync === "erp5" && gadget.state.storage_url) {
            // start import from erp5 now
            return gadget.setSetting("hateoas_url", gadget.state.storage_url)
              .push(function () {
                return gadget.state.erp5_gadget.createJio();
              })
              .push(function () {
                // force login if not logged yet
                return gadget.state.erp5_gadget.get("document2");
              })
              .push(undefined, function () {
                return false;
              })
              .push(function () {
                // load monitoring information.
                return gadget.state.erp5_gadget.getAttachment(
                  'hosting_subscription_module',
                  gadget.state.storage_url + 'hosting_subscription_module'
                    + "/Base_getMonitoringInstanceParameterDictAsJson"
                );
              })
              .push(undefined, function () {
                gadget.state.message
                  .innerHTML = notify_msg_template({
                    status: 'error',
                    message: 'Error: Failed to get Monitor Configuration from URL: ' +
                      gadget.state.storage_url
                  });
                return undefined;
              })
              .push(function (result) {
                if (result !== undefined) {
                  return importMonitorConfiguration(gadget, result);
                }
              });
          }
        });
    });
}(window, rJS, RSVP, jsen, Rusha, Handlebars, atob));