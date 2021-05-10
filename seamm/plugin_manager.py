# -*- coding: utf-8 -*-

import logging
import pprint
import stevedore

"""A plugin manager based on Stevedore"""

logger = logging.getLogger(__name__)


class PluginManager(object):
    def __init__(self, namespace):
        logger.info("Initializing extensions for {}".format(namespace))

        self.namespace = namespace
        self.manager = stevedore.extension.ExtensionManager(
            namespace=self.namespace,
            invoke_on_load=True,
            on_load_failure_callback=self.load_failure,
        )
        self._plugins = {}

        logger.info(
            "Found {:d} extensions in '{:s}': {}".format(
                len(self.manager.names()), self.namespace, self.manager.names()
            )
        )

        logger.debug("Processing extensions")

        for name in self.manager.names():
            logger.debug("    extension name: {}".format(name))
            extension = self.manager[name].obj
            logger.debug("  extension object: {}".format(extension))
            data = extension.description()
            logger.debug("    extension data:")
            logger.debug(pprint.pformat(data))
            logger.debug("")
            group = data["group"]
            if group in self._plugins:
                self._plugins[group].append(name)
            else:
                self._plugins[group] = [name]

    def load_failure(self, mgr, ep, err):
        """Called when the extension manager can't load an extension"""
        logger.warning("Could not load %r: %s", ep.name, err)

    def get(self, name):
        return self.manager[name].obj

    def groups(self):
        return sorted(list(self._plugins.keys()))

    def plugins(self, group):
        return sorted(list(self._plugins[group]))
