"""
/***************************************************************************
Name                 : STDM QGIS Loader
Description          : STDM QGIS Loader
Date                 : 23/May/2013 
copyright            : (C) 2013 by John Gitau
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

import os.path, string

from PyQt4.QtCore import * 
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *
from PyQt4.QtNetwork import *

from qgis.core import *
from qgis.gui import *

import resources_rc
from ui import (
                loginDlg, 
                changePwdDlg, 
                manageAccountsDlg, 
                contentAuthDlg,
                newSTRWiz, 
                ViewSTRWidget, 
                AdminUnitSelector, 
                FarmerEntityBrowser,
                SurveyEntityBrowser,
                PersonDocumentGenerator
                )
import data
from data import (
                  STDMDb, 
                  Content,
                  spatial_tables
                  )
from navigation import (
                        STDMAction,
                        QtContainerLoader,
                        ContentGroup,
                        TableContentGroup
                        )
from mapping import (
                     StdmMapToolCreateFeature
                     )
from utils import getIndex
from mapping.utils import pg_layerNamesIDMapping
from composer import ComposerWrapper

class stdmqgisloader:
    
    viewSTRWin = None
    
    def __init__(self,iface):        
        self.iface = iface
        
        #Initialize loader
        self.toolbarLoader = None
        
        #setup locale
        pluginDir = os.path.dirname(__file__)
        localePath = ""
        locale = QSettings().value("locale/userLocale")[0:2]
        if QFileInfo(pluginDir).exists():
            #Replace forward slash with backslash
            pluginDir = string.replace(pluginDir, "\\", "/")
            localePath = pluginDir + "/i18n/stdm_%s.qm"%(locale,)            
        if QFileInfo(localePath).exists():                 
            self.translator = QTranslator()
            self.translator.load(localePath)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
                
        #Initialize the property management window
        self.propManageWindow = None
        
        #STDM Tables
        self.stdmTables = []
        
    def initGui(self):
        #Initial actions on starting up the application
        self.loginAct = STDMAction(QIcon(":/plugins/stdm/images/icons/login.png"), \
        QApplication.translate("LoginToolbarAction","Login"), self.iface.mainWindow(),
        "CAA4F0D9-727F-4745-A1FC-C2173101F711")
        self.aboutAct = STDMAction(QIcon(":/plugins/stdm/images/icons/information.png"), \
        QApplication.translate("AboutToolbarAction","About"), self.iface.mainWindow(),
        "137FFB1B-90CD-4A6D-B49E-0E99CD46F784")
        #Define actions that are available to all logged in users
        self.logoutAct = STDMAction(QIcon(":/plugins/stdm/images/icons/logout.png"), \
        QApplication.translate("LogoutToolbarAction","Logout"), self.iface.mainWindow(),
        "EF3D96AF-F127-4C31-8D9F-381C07E855DD")
        self.changePasswordAct = STDMAction(QIcon(":/plugins/stdm/images/icons/change_password.png"), \
        QApplication.translate("ChangePasswordToolbarAction","Change Password"), self.iface.mainWindow(),
        "8C425E0E-3761-43F5-B0B2-FB8A9C3C8E4B")
        # connect the actions to their respective methods
        QObject.connect(self.loginAct, SIGNAL("triggered()"), self.login) 
        QObject.connect(self.changePasswordAct, SIGNAL("triggered()"), self.changePassword)
        QObject.connect(self.logoutAct, SIGNAL("triggered()"), self.logout)
        self.initToolbar()
        
    def getThemeIcon(self, theName):        
        # get the icon from the best available theme
        myCurThemePath = QgsApplication.activeThemePath() + "/plugins/" + theName;
        myDefThemePath = QgsApplication.defaultThemePath() + "/plugins/" + theName;
        myQrcPath = ":/plugins/stdm/" + theName;
        if QFile.exists(myCurThemePath):            
            return QIcon(myCurThemePath)
        elif QFile.exists(myDefThemePath):
            return QIcon(myDefThemePath)
        elif QFile.exists(myQrcPath):
            return QIcon(myQrcPath)
        else:
            return QIcon()
        
    def initToolbar(self):
        #Load initial STDM toolbar    
        self.stdmInitToolbar = self.iface.addToolBar("STDM")  
        self.stdmInitToolbar.setObjectName("STDM")
        #Add actions to the toolbar
        self.stdmInitToolbar.addAction(self.loginAct)                
                                
        self.stdmInitToolbar.addSeparator()
        self.stdmInitToolbar.addAction(self.aboutAct)   
   
    def unload(self):                
        #Remove the STDM toolbar
        del self.stdmInitToolbar
        
        #Remove connection info
        self.logoutCleanUp()
        
    def login(self):
        '''
        Show login dialog
        '''          
        frmLogin = loginDlg(self)
        retstatus = frmLogin.exec_()
        
        if retstatus == QDialog.Accepted:            
            #Assign the connection object
            data.app_dbconn = frmLogin.dbConn            
            #Initialize the whole STDM database
            db = STDMDb.instance()        
            #Load logout and change password actions
            self.stdmInitToolbar.insertAction(self.loginAct,self.logoutAct)
            self.stdmInitToolbar.insertAction(self.loginAct,self.changePasswordAct)
            self.loginAct.setEnabled(False)   
            
            #Get STDM tables
            self.stdmTables = spatial_tables()                         
            
            try:
                self.loadModules()
            except Exception as ex:
                QMessageBox.warning(self.iface.mainWindow(),QApplication.translate("STDM","Error"),ex.message)
            
    def loadModules(self):
        '''
        Define and add modules to the menu and/or toolbar using the module loader
        '''
        self.toolbarLoader = QtContainerLoader(self.iface.mainWindow(),self.stdmInitToolbar,self.logoutAct)
        
        #Connect to the content added signal
        #self.toolbarLoader.contentAdded.connect(self.onContentAdded)
        
        #Define containers for grouping actions
        adminBtn = QToolButton()
        adminObjName = QApplication.translate("ToolbarAdminSettings","Admin Settings")
        #Required by module loader for those widgets that need to be inserted into the container
        adminBtn.setObjectName(adminObjName)              
        adminBtn.setToolTip(adminObjName)
        adminBtn.setIcon(QIcon(":/plugins/stdm/images/icons/settings.png"))
        adminBtn.setPopupMode(QToolButton.InstantPopup)
        
        adminMenu = QMenu(adminBtn) 
        adminBtn.setMenu(adminMenu)  
        
        #Separator definition
        tbSeparator = QAction(self.iface.mainWindow())   
        tbSeparator.setSeparator(True)    
        
        #Define actions 
        self.contentAuthAct = QAction(QIcon(":/plugins/stdm/images/icons/content_auth.png"), \
        QApplication.translate("ContentAuthorizationToolbarAction","Content Authorization"), self.iface.mainWindow())
        
        self.usersAct = QAction(QIcon(":/plugins/stdm/images/icons/users_manage.png"), \
        QApplication.translate("ManageUsersToolbarAction","Manage Users-Roles"), self.iface.mainWindow())  
        
        self.manageAdminUnitsAct = QAction(QIcon(":/plugins/stdm/images/icons/manage_admin_units.png"), \
        QApplication.translate("ManageAdminUnitsToolbarAction","Manage Administrative Units"), self.iface.mainWindow())             
        
        self.surveyAct = QAction(QIcon(":/plugins/stdm/images/icons/survey.png"), \
        QApplication.translate("NewSurveyToolbarAction","Survey"), self.iface.mainWindow()) 
        
        self.farmerAct = QAction(QIcon(":/plugins/stdm/images/icons/farmer.png"), \
        QApplication.translate("NewFarmerToolbarAction","Farmer"), self.iface.mainWindow())    
        
        self.docDesignerAct = QAction(QIcon(":/plugins/stdm/images/icons/cert_designer.png"), \
        QApplication.translate("DocumentDesignerAction","Document Designer"), self.iface.mainWindow()) 
        
        self.docGeneratorAct = QAction(QIcon(":/plugins/stdm/images/icons/generate_document.png"), \
        QApplication.translate("DocumentGeneratorAction","Document Generator"), self.iface.mainWindow())
        
        #Activate spatial unit management tools
        self.spatialEditorAct = QAction(QIcon(":/plugins/stdm/images/icons/edit24.png"), \
        QApplication.translate("SpatialEditorAction","Toggle Spatial Unit Editing"), self.iface.mainWindow()) 
        self.spatialEditorAct.setCheckable(True)
        
        self.createFeatureAct = QAction(QIcon(":/plugins/stdm/images/icons/create_feature.png"), \
        QApplication.translate("CreateFeatureAction","Create Spatial Unit"), self.iface.mainWindow()) 
        self.createFeatureAct.setCheckable(True)
        self.createFeatureAct.setVisible(False)
        
        #SaveEdits action; will not be registered since it is associated with the CreateFeature action in order to be relevant
        self.saveEditsAct = QAction(QIcon(":/plugins/stdm/images/icons/save_tb.png"), \
        QApplication.translate("CreateFeatureAction","Save Edits"), self.iface.mainWindow()) 
        
        self.newSTRAct = QAction(QIcon(":/plugins/stdm/images/icons/new_str.png"), \
        QApplication.translate("NewSTRToolbarAction","New Social Tenure Relationship"), self.iface.mainWindow())  
        
        self.viewSTRAct = QAction(QIcon(":/plugins/stdm/images/icons/view_str.png"), \
        QApplication.translate("ViewSTRToolbarAction","View Social Tenure Relationship"), self.iface.mainWindow()) 
        
        #Connect the slots for the actions above
        QObject.connect(self.contentAuthAct, SIGNAL("triggered()"),self.contentAuthorization)
        QObject.connect(self.usersAct, SIGNAL("triggered()"),self.manageAccounts)     
        QObject.connect(self.manageAdminUnitsAct, SIGNAL("triggered()"),self.onManageAdminUnits)
        QObject.connect(self.surveyAct, SIGNAL("triggered()"),self.onManageSurvey)
        QObject.connect(self.farmerAct, SIGNAL("triggered()"),self.onManageFarmer)
        self.docDesignerAct.triggered.connect(self.onDocumentDesigner)
        self.docGeneratorAct.triggered.connect(self.onDocumentGeneratorByPerson)
        QObject.connect(self.spatialEditorAct, SIGNAL("toggled(bool)"),self.onToggleSpatialEditing)
        QObject.connect(self.saveEditsAct, SIGNAL("triggered()"),self.onSaveEdits)
        QObject.connect(self.createFeatureAct, SIGNAL("triggered()"),self.onCreateFeature)
        '''
        QObject.connect(self.newSTRAct, SIGNAL("triggered()"), self.newSTR)
        QObject.connect(self.viewSTRAct, SIGNAL("triggered()"), self.onViewSTR)
        '''
        
        #Create content items
        contentAuthCnt = ContentGroup.contentItemFromQAction(self.contentAuthAct)
        contentAuthCnt.code = "E59F7CC1-0D0E-4EA2-9996-89DACBD07A83"
        
        userRoleMngtCnt = ContentGroup.contentItemFromQAction(self.usersAct)
        userRoleMngtCnt.code = "0CC4FB8F-70BA-4DE8-8599-FD344A564EB5"
        
        adminUnitsCnt = ContentGroup.contentItemFromQAction(self.manageAdminUnitsAct)
        adminUnitsCnt.code = "770EAC75-2BEC-492E-8703-34674054C246"
        
        surveyCnt = ContentGroup.contentItemFromQAction(self.surveyAct)
        surveyCnt.code = "5620049B-983A-4F85-B0D6-9D83925CC45E"
        
        farmerCnt = ContentGroup.contentItemFromQAction(self.farmerAct)
        farmerCnt.code = "99EA7671-85CF-40D6-B417-A3CC49D5A594"
        
        documentDesignerCnt = ContentGroup.contentItemFromQAction(self.docDesignerAct)
        documentDesignerCnt.code = "C4826C19-2AE3-486E-9FF0-32C00A0A517F"
        
        documentGeneratorCnt = ContentGroup.contentItemFromQAction(self.docGeneratorAct)
        documentGeneratorCnt.code = "4C0C7EF2-5914-4FDE-96CB-089D44EDDA5A"
        
        spatialEditingCnt = ContentGroup.contentItemFromQAction(self.spatialEditorAct)
        spatialEditingCnt.code = "4E945EE7-D6F9-4E1C-A4AA-0C7F1BC67224"
        
        createFeatureCnt = ContentGroup.contentItemFromQAction(self.createFeatureAct)
        createFeatureCnt.code = "71CFDB15-EDB5-410D-82EA-0E982971BC51"
        
        #Create content groups and add items
        username = data.app_dbconn.User.UserName
        
        self.contentAuthCntGroup = ContentGroup(username)
        self.contentAuthCntGroup.addContentItem(contentAuthCnt)
        self.contentAuthCntGroup.setContainerItem(self.contentAuthAct)
        self.contentAuthCntGroup.register()
        
        self.userRoleCntGroup = ContentGroup(username)
        self.userRoleCntGroup.addContentItem(userRoleMngtCnt)
        self.userRoleCntGroup.setContainerItem(self.usersAct)
        self.userRoleCntGroup.register()
        
        self.adminUnitsCntGroup = ContentGroup(username)
        self.adminUnitsCntGroup.addContentItem(adminUnitsCnt)
        self.adminUnitsCntGroup.setContainerItem(self.manageAdminUnitsAct)
        self.adminUnitsCntGroup.register()
        
        self.spatialEditingCntGroup = ContentGroup(username,self.spatialEditorAct)
        self.spatialEditingCntGroup.addContentItem(spatialEditingCnt)
        self.spatialEditingCntGroup.register()
        
        self.createFeatureCntGroup = ContentGroup(username,self.createFeatureAct)
        self.createFeatureCntGroup.addContentItem(createFeatureCnt)
        self.createFeatureCntGroup.register()
        
        self.surveyCntGroup = TableContentGroup(username,self.surveyAct.text(),self.surveyAct)
        self.surveyCntGroup.createContentItem().code = "A7783C39-1A5B-4F79-81C2-639C2EA3E8A3"
        self.surveyCntGroup.readContentItem().code = "CADFC838-DA3C-44C5-A6A8-3B2FC4CA8464"
        self.surveyCntGroup.updateContentItem().code = "B42AC2C5-7CF5-48E6-A37F-EAE818FBC9BC"
        self.surveyCntGroup.deleteContentItem().code = "C916ACF3-30E6-45C3-B8E1-22E56D0AFB3E"
        self.surveyCntGroup.register()
        
        self.farmerCntGroup = TableContentGroup(username,self.farmerAct.text(),self.farmerAct)
        self.farmerCntGroup.createContentItem().code = "07402A75-89BF-4EB2-A161-FE6EE875AD5B"
        self.farmerCntGroup.readContentItem().code = "1ACF4D60-4592-4ED2-A479-C9D3E409B112"
        self.farmerCntGroup.updateContentItem().code = "05E3DEAA-77A2-4556-ABF9-016427EE607F"
        self.farmerCntGroup.deleteContentItem().code = "B2BC55EF-A0AF-45C7-A4BE-766839C910A3"
        self.farmerCntGroup.register()
        
        self.docDesignerCntGroup = ContentGroup(username,self.docDesignerAct)
        self.docDesignerCntGroup.addContentItem(documentDesignerCnt)
        self.docDesignerCntGroup.register()
        
        self.docGeneratorCntGroup = ContentGroup(username,self.docGeneratorAct)
        self.docGeneratorCntGroup.addContentItem(documentGeneratorCnt)
        self.docGeneratorCntGroup.register()
        
        self.toolbarLoader.addContent(self.contentAuthCntGroup,[adminMenu,adminBtn])
        self.toolbarLoader.addContent(self.userRoleCntGroup, [adminMenu,adminBtn])
        self.toolbarLoader.addContent(self.adminUnitsCntGroup)
        self.toolbarLoader.addContent(tbSeparator)
        self.toolbarLoader.addContent(self.docDesignerCntGroup)
        self.toolbarLoader.addContent(self.docGeneratorCntGroup)
        self.toolbarLoader.addContent(tbSeparator)
        self.toolbarLoader.addContent(self.surveyCntGroup)
        self.toolbarLoader.addContent(self.farmerCntGroup)
        self.toolbarLoader.addContent(tbSeparator)
        self.toolbarLoader.addContent(self.spatialEditingCntGroup)
        self.toolbarLoader.addContent(self.createFeatureCntGroup)
        
        #Group spatial editing tools together
        self.spatialEditingGroup = QActionGroup(self.iface.mainWindow())
        self.spatialEditingGroup.addAction(self.createFeatureAct)
        
        self.configureMapTools()
        
        #Load all the content in the container
        self.toolbarLoader.loadContent()
        
    def configureMapTools(self):
        '''
        Configure properties of STDM map tools.
        '''
        self.mapToolCreateFeature = StdmMapToolCreateFeature(self.iface)
        self.mapToolCreateFeature.setAction(self.createFeatureAct)
        
    def onActionAuthorised(self,name):
        '''
        This slot is raised when a toolbar action is authorised for access by the currently
        logged in user.
        '''        
        pass    
            
    def onContentAdded(self,stdmAction):  
        '''
        Slot raised when an STDMAction has been added to its corresponding container.
        '''
        if stdmAction.Name == self.createFeatureAct.Name:        
            #Insert SaveEdits action
            self.stdmInitToolbar.insertAction(self.createFeatureAct,self.saveEditsAct) 
            
    def onFinishedLoadingContent(self):
        '''
        This slot is raised once the module loader has finished loading content items.        
        ''' 
        if self.propManageWindow != None:
            self.iface.addDockWidget(Qt.RightDockWidgetArea,self.propManageWindow)
        
    def manageAccounts(self):
        '''
        Slot for showing the user and role accounts management window
        '''
        frmUserAccounts = manageAccountsDlg(self)
        frmUserAccounts.exec_()
        
    def contentAuthorization(self):
        '''
        Slot for showing the content authorization dialog
        '''
        frmAuthContent = contentAuthDlg(self)
        frmAuthContent.exec_()
        
    def changePassword(self):
        '''
        Slot for changing password
        '''    
        #Load change password dialog
        frmPwdDlg = changePwdDlg(self)
        frmPwdDlg.exec_()
           
    def onShowHidePropertyWindow(self,visible):
        '''
        Slot raised when the user checks or unchecks the action for 
        showing/hiding the property manager window
        '''
        if visible:
            self.propMngtAct.setChecked(True)
        else:
            self.propMngtAct.setChecked(False)
            
    def newSTR(self):
        '''
        Slot for showing the wizard for defining a new social
        tenure relationship
        '''
        frmNewSTR = newSTRWiz(self)
        frmNewSTR.exec_()
        
    def onManageAdminUnits(self):
        '''
        Slot for showing administrative unit selector dialog.
        '''
        frmAdminUnitSelector = AdminUnitSelector(self.iface.mainWindow())
        frmAdminUnitSelector.setManageMode(True)
        frmAdminUnitSelector.exec_()
        
    def onManageSurvey(self):
        '''
        Slot raised to show form for entering new survey.
        '''
        surveyBrowser = SurveyEntityBrowser(self.surveyCntGroup,self.iface.mainWindow())
        surveyBrowser.exec_()
        
    def onManageFarmer(self):
        '''
        Slot raised to show form for entering new farmer details.
        '''
        farmerBrowser = FarmerEntityBrowser(self.farmerCntGroup,self.iface.mainWindow())
        farmerBrowser.exec_()
        
    def onDocumentDesigner(self):
        """
        Slot raised to show new print composer with additional tools for designing 
        map-based documents.
        """
        documentComposer = self.iface.createNewComposer("STDM Document Designer")
        
        #Embed STDM customizations
        composerWrapper = ComposerWrapper(documentComposer)
        composerWrapper.configure()
        
    def onDocumentGeneratorByPerson(self):
        """
        Document generator by person dialog.
        """
        personDocGenDlg = PersonDocumentGenerator(self.iface,self.iface.mainWindow())
        personDocGenDlg.exec_()
        
    def onSaveEdits(self):
        '''
        Slot raised to save changes to STDM layers.
        '''
        currLayer = self.iface.activeLayer()
        
        if currLayer == None:
            return
        
        if not isinstance(currLayer,QgsVectorLayer):
            return 
        
        #Assert if layer is from the SDTM database
        if not self.isSTDMLayer(currLayer):
            return 
        
        if not currLayer.commitChanges():
            self.iface.messageBar().clearWidgets()
            self.iface.messageBar().pushMessage(QApplication.translate("STDMPlugin","Save STDM Layer"),
                                                QApplication.translate("STDMPlugin","Could not commit changes to {0} layer.".format(currLayer.name())),
                                                level=QgsMessageBar.CRITICAL)
            
        currLayer.startEditing()
        currLayer.triggerRepaint()
            
    def onToggleSpatialEditing(self,toggled):
        '''
        Slot raised on toggling to activate/deactivate editing, and load corresponding 
        spatial tools.
        '''
        currLayer = self.iface.activeLayer()
        
        if currLayer != None:
            self.toggleEditing(currLayer)
            
        else:
            self.spatialEditorAct.setChecked(False)
            
        if not toggled:
            self.createFeatureAct.setChecked(False)
            self.createFeatureAct.setVisible(False)
        
    def toggleEditing(self,layer):
        '''
        Actual implementation which validates and creates/ends edit sessions.
        '''
        if not isinstance(layer,QgsVectorLayer):
            return False
        
        teResult = True
        
        #Assert if layer is from the SDTM database
        if not self.isSTDMLayer(layer):
            self.spatialEditorAct.setChecked(False)
            self.iface.messageBar().clearWidgets()
            self.iface.messageBar().pushMessage(QApplication.translate("STDMPlugin","Non-SDTM Layer"),
                                                QApplication.translate("STDMPlugin","Selected layer is not from the STDM database."),
                                                level=QgsMessageBar.CRITICAL)
                
            return False
        
        if not layer.isEditable() and not layer.isReadOnly():
            if not (layer.dataProvider().capabilities() & QgsVectorDataProvider.EditingCapabilities):
                self.spatialEditorAct.setChecked(False)
                self.spatialEditorAct.setEnabled(False)
                self.iface.messageBar().pushMessage(QApplication.translate("STDMPlugin","Start Editing Failed"),
                                                    QApplication.translate("STDMPlugin","Provider cannot be opened for editing"),
                                                    level=QgsMessageBar.CRITICAL)
                
                return False
            
            #Enable/show spatial editing tools
            self.createFeatureAct.setVisible(True)
            
            layer.startEditing()
            
        elif layer.isModified():
            saveResult = QMessageBox.information(self.iface.mainWindow(), 
                                                 QApplication.translate("STDMPlugin","Stop Editing"), 
                                                 QApplication.translate("STDMPlugin",
                                                                        "Do you want to save changes to {0} layer?".format(layer.name())), \
                                                 QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
            
            if saveResult == QMessageBox.Cancel:
                teResult = False
                
            elif saveResult == QMessageBox.Save:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                
                if not layer.commitChanges():
                    teResult = False
                    
                layer.triggerRepaint()
                
                QApplication.restoreOverrideCursor()
                
            else:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                
                self.iface.mapCanvas().freeze(True)
                
                if not layer.rollBack():
                    self.iface.messageBar().pushMessage(QApplication.translate("STDMPlugin","Error"),
                                                    QApplication.translate("STDMPlugin","Problems during rollback"),
                                                    level=QgsMessageBar.CRITICAL)
                    teResult = False
                    
                self.iface.mapCanvas().freeze(False)
                
                layer.triggerRepaint()
                
                QApplication.restoreOverrideCursor()
        
        #Layer has not been modified       
        else:
            self.iface.mapCanvas().freeze(True)
            layer.rollBack()
            self.iface.mapCanvas().freeze(False)
            teResult = True
            layer.triggerRepaint()
        
        '''
        #Disable/hide related tools   
        if not teResult and layer == self.iface.activeLayer():
            self.createFeatureAct.setVisible(False)
        '''
                    
        return teResult
        
    def onCreateFeature(self):
        '''
        Slot raised to activate the digitization process of creating a new feature.
        '''
        self.iface.mapCanvas().setMapTool(self.mapToolCreateFeature)
         
    def onViewSTR(self):
        '''
        Slot for showing widget that enables users to browse 
        existing STRs.
        '''
        if self.viewSTRWin == None:
            self.viewSTRWin = ViewSTRWidget(self)
            self.viewSTRWin.show()
        else:
            self.viewSTRWin.showNormal()
            self.viewSTRWin.setFocus()
            
    def isSTDMLayer(self,layer):
        '''
        Return whether the layer is an STDM layer.
        '''
        if layer.id() in pg_layerNamesIDMapping().reverse:
            return True
        
        return False
            
    def logout(self):
        '''
        Logout the user and remove default user buttons when logged in
        '''
        self.stdmInitToolbar.removeAction(self.logoutAct)
        self.stdmInitToolbar.removeAction(self.changePasswordAct)
        self.loginAct.setEnabled(True)
        self.logoutCleanUp()
        
    def removeSTDMLayers(self):
        '''
        Remove all STDM layers from the map registry.
        '''
        mapLayers = QgsMapLayerRegistry.instance().mapLayers().values()
            
        for layer in mapLayers:
            if self.isSTDMLayer(layer):
                QgsMapLayerRegistry.instance().removeMapLayer(layer)
                
        self.stdmTables = []
        
    def logoutCleanUp(self):
        '''
        Clear database connection references and content items
        '''
        #Remove STDM layers
        self.removeSTDMLayers()
        
        #Clear singleton ref for SQLALchemy connections
        if data.app_dbconn!= None:            
            STDMDb.cleanUp()     
                   
        #Remove database reference 
        data.app_dbconn = None  
              
        if self.toolbarLoader != None:
            self.toolbarLoader.unloadContent()
            
        #Reset property management window
        if self.propManageWindow != None:
            self.iface.removeDockWidget(self.propManageWindow)
            del self.propManageWindow
            self.propManageWindow = None
            
        #Reset View STR Window
        if self.viewSTRWin != None:
            del self.viewSTRWin
            self.viewSTRWin = None
            
        
        
        
        
        
        
        
        
        
