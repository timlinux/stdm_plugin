"""
/***************************************************************************
Name                 : Configuration for custom STDM data source.
Date                 : 20/May/2014
copyright            : (C) 2014 by John Gitau
email                : gkahiu@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from stdm.utils import getIndex,ReverseDict

__all__ = ["ComposerDataSource"]

class ComposerDataSource(object):
    """
    Container for data source settings.
    """
    def __init__(self,dataSourceName="",category = ""):
        self._dataSourceName = dataSourceName
        self._dataSourceCategory = category
        self._dataFieldmappings = ReverseDict()
        self._spatialFieldsConfig = None
        
    def setName(self,dataSourceName):
        """
        Sets the data source name.
        """
        self._dataSourceName = dataSourceName
        
    def name(self):
        """
        Returns the data source name.
        """
        return self._dataSourceName
    
    def category(self):
        """
        Returns the category of the data source.
        """
        return self._dataSourceCategory
    
    def setCategory(self,category):
        """
        Set the category of the data source.
        """
        self._dataSourceCategory = category
        
    def setSpatialFieldsConfig(self,spFieldsConfig):
        """
        Set the spatial fields configuration object
        """
        self._spatialFieldsConfig = spFieldsConfig
    
    def addDataFieldMapping(self,dataField,composerItemId):
        """
        Add the name of the data field.
        """
        self._dataFieldmappings[dataField] = composerItemId
        
    def dataFieldMappings(self):
        """
        Returns the collection of data field mappings.
        """
        return self._dataFieldmappings
        
    def clear(self):
        """
        Clears the data source name and removes all data field mappings.
        """
        self._dataSourceName = ""
        self._dataFieldmappings = ReverseDict()
        
    def dataFieldName(self,composerItemId):
        """
        Returns the data field name corresponding to the composer item id.
        """
        if composerItemId in self._dataFieldmappings.reverse:
            return self._dataFieldmappings.reverse[composerItemId]
        else:
            None
            
    def composerItemId(self,dataField):
        """
        Returns the composer item unique identifier corresponding to the given
        field.
        """
        if dataField in self._dataFieldmappings:
            return self._dataFieldmappings[dataField]
        else:
            return None
        
    def sqlSelectStatement(self):
        """
        Returns a sql select statement based on the data source and fields specified,as
        well as the spatial fields.
        """
        dataFields = self._dataFieldmappings.keys()
        
        #Get spatial fields and embed into the dataFields list
        if self._spatialFieldsConfig != None:
            spatialFieldsCollection = self._spatialFieldsConfig.spatialFieldsMapping().values()
            
            for spfEntry in spatialFieldsCollection:
                spFields = [spm.spatialField() for spm in spfEntry]
                labelFields = [spm.labelField() for spm in spfEntry]
                dataFields.extend(spFields)
                dataFields.extend(labelFields)
        
        if len(dataFields) == 0:
            return ""
        
        #Ensure you only have unique fields
        dataFieldsSet = set(dataFields)
        
        dtFieldsStr = ",".join(dataFieldsSet)
        
        return "SELECT {0} FROM {1}".format(dtFieldsStr,self._dataSourceName)
    
    @staticmethod    
    def create(domDocument):
        """
        Create an instance of the ComposerDataSource object from a DOM document.
        Returns None if the domDocument is invalid.
        """
        dataSourceElem = domDocument.documentElement().firstChildElement("DataSource") 
        
        if dataSourceElem == None:
            return None
        
        dataSourceName = dataSourceElem.attribute("name")
        dataSourceCategory = dataSourceElem.attribute("category")
        composerDS = ComposerDataSource(dataSourceName,dataSourceCategory)
        
        #Get data fields
        dataFieldList = dataSourceElem.elementsByTagName("DataField")
        numItems = dataFieldList.length()
        
        for i in range(numItems):
            dataFieldElement = dataFieldList.item(i).toElement()
            dataFieldName = dataFieldElement.attribute("name")
            composerItemId = dataFieldElement.attribute("itemid")
            
            composerDS.addDataFieldMapping(dataFieldName, composerItemId)
            
        return composerDS
        
    @staticmethod   
    def domElement(composerWrapper,domDocument):
        """
        Helper method that creates a data source DOM element from a composer wrapper instance.
        """
        from stdm.ui import ComposerFieldSelector
        
        dataSourceElement = domDocument.createElement("DataSource")
        dataSourceElement.setAttribute("name",composerWrapper.selectedDataSource())
        dataSourceElement.setAttribute("category",composerWrapper.selectedDataSourceCategory())
        
        #Get the configured field names
        for uuid,fieldWidget in composerWrapper.widgetMappings().iteritems():
            """
            Assert whether the item exists in the composition since the 'itemRemoved' signal cannot be used to 
            delete items from the collection as it only returns a QObject instead of a QgsComposerItem subclass.
            """
            composerItem = composerWrapper.composition().getComposerItemByUuid(uuid)
            
            if composerItem != None:
                if isinstance(fieldWidget,ComposerFieldSelector):
                    fieldName = fieldWidget.fieldName()
                    
                    fieldElement = domDocument.createElement("DataField")
                    fieldElement.setAttribute("itemid",uuid)
                    fieldElement.setAttribute("name",fieldName)
                    
                    dataSourceElement.appendChild(fieldElement)
                    
        return dataSourceElement
        