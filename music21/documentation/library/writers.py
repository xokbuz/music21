# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:         convertIPythonNotebooksToReST.py
# Purpose:      music21 documentation IPython notebook to ReST converter
#
# Authors:      Josiah Wolf Oberholtzer
#
# Copyright:    Copyright © 2013-14 Michael Scott Cuthbert and the music21 Project
# License:      LGPL or BSD, see license.txt
#-------------------------------------------------------------------------------

import os
import re

from music21 import common
from music21 import exceptions21

class DocumentationWritersException(exceptions21.Music21Exception):
    pass


class ReSTWriter(object):
    '''
    Abstract base class for ReST writers.
    
    Call .run() on the object to make it work.
    '''

    def run(self):
        raise NotImplemented

    ### PUBLIC METHODS ###

    def write(self, filePath, rst): #
        '''
        Write ``lines`` to ``filePath``, only overwriting an existing file
        if the content differs.
        '''
        shouldWrite = True
        if os.path.exists(filePath):
            with open(filePath, 'r') as f:
                oldRst = f.read()
            if rst == oldRst:
                shouldWrite = False
        if shouldWrite:
            with open(filePath, 'w') as f:
                f.write(rst)
            print('\tWROTE   {0}'.format(common.relativepath(filePath)))
        else:
            print('\tSKIPPED {0}'.format(common.relativepath(filePath)))


class ModuleReferenceReSTWriter(ReSTWriter):
    '''
    Writes module reference ReST files, and their index ReST file.
    '''

    def run(self):
        from music21 import documentation # @UnresolvedImport
        moduleReferenceDirectoryPath = os.path.join(
            documentation.__path__[0],
            'source',
            'moduleReference',
            )
        referenceNames = []
        for module in [x for x in documentation.ModuleIterator()]:
            moduleDocumenter = documentation.ModuleDocumenter(module)
            if not moduleDocumenter.classDocumenters \
                and not moduleDocumenter.functionDocumenters:
                continue
            rst = '\n'.join(moduleDocumenter.run())
            referenceName = moduleDocumenter.referenceName
            referenceNames.append(referenceName)
            fileName = '{0}.rst'.format(referenceName)
            filePath = os.path.join(
                moduleReferenceDirectoryPath,
                fileName,
                )
            self.write(filePath, rst)

        lines = []
        lines.append('.. moduleReference:')
        lines.append('')
        lines.append('.. WARNING: DO NOT EDIT THIS FILE:')
        lines.append('   AUTOMATICALLY GENERATED.')
        lines.append('')
        lines.append('Module Reference')
        lines.append('================')
        lines.append('')
        lines.append('.. toctree::')
        lines.append('   :maxdepth: 1')
        lines.append('')
        for referenceName in sorted(referenceNames):
            lines.append('   {0}'.format(referenceName))
        rst = '\n'.join(lines)
        indexFilePath = os.path.join(
            moduleReferenceDirectoryPath,
            'index.rst',
            )
        self.write(indexFilePath, rst)


class CorpusReferenceReSTWriter(ReSTWriter):
    '''
    Write the corpus reference ReST file.
    '''
    def run(self):
        from music21 import documentation # @UnresolvedImport
        systemReferenceDirectoryPath = os.path.join(
            documentation.__path__[0],
            'source',
            'systemReference',
            )
        corpusReferenceFilePath = os.path.join(
            systemReferenceDirectoryPath,
            'referenceCorpus.rst',
            )
        lines = documentation.CorpusDocumenter().run()
        rst = '\n'.join(lines)
        self.write(corpusReferenceFilePath, rst)


class IPythonNotebookReSTWriter(ReSTWriter):
    '''
    Converts IPython notebooks into ReST, and handles their associated image
    files.

    This class wraps the 3rd-party ``nbconvert`` Python script.
    '''

    def run(self):
        from music21 import documentation # @UnresolvedImport
        ipythonNotebookFilePaths = [x for x in
            documentation.IPythonNotebookIterator()]
        for ipythonNotebookFilePath in ipythonNotebookFilePaths:
            nbConvertReturnCode = self.convertOneNotebook(ipythonNotebookFilePath)
            if nbConvertReturnCode is True:
                self._cleanupNotebookAssets(ipythonNotebookFilePath)
                print('\tWROTE   {0}'.format(common.relativepath(
                    ipythonNotebookFilePath)))
            else:
                print('\tSKIPPED {0}'.format(common.relativepath(
                    ipythonNotebookFilePath)))

    ### PRIVATE METHODS ###

    def _cleanupNotebookAssets(self, ipythonNotebookFilePath):
        notebookFileNameWithoutExtension = os.path.splitext(
            os.path.basename(ipythonNotebookFilePath))[0]
        notebookParentDirectoryPath = os.path.abspath(
            os.path.dirname(ipythonNotebookFilePath),
            )
        imageFileDirectoryName = notebookFileNameWithoutExtension + '_files'
        imageFileDirectoryPath = os.path.join(
            notebookParentDirectoryPath,
            imageFileDirectoryName,
            )
        for fileName in os.listdir(imageFileDirectoryPath):
            if fileName.endswith('.text'):
                filePath = os.path.join(
                    imageFileDirectoryPath,
                    fileName,
                    )
                os.remove(filePath)

    def convertOneNotebook(self, ipythonNotebookFilePath):
        '''
        converts one .ipynb file to .rst using nbconvert.

        returns True if IPythonNotebook was converted.
        returns False if IPythonNotebook's converted .rst file is newer than the .ipynb file.

        sends AssertionError if ipythonNotebookFilePath does not exist.
        '''
        if '-checkpoint' in ipythonNotebookFilePath:
            return False
        
        if not os.path.exists(ipythonNotebookFilePath):
            raise DocumentationWritersException('No iPythonNotebook with filePath %s' % ipythonNotebookFilePath)
        notebookFileNameWithoutExtension = os.path.splitext(
            os.path.basename(ipythonNotebookFilePath))[0]
        notebookParentDirectoryPath = os.path.abspath(
            os.path.dirname(ipythonNotebookFilePath),
            )
        imageFileDirectoryName = notebookFileNameWithoutExtension + '_files'
        rstFileName = notebookFileNameWithoutExtension + '.rst'
        rstFilePath = os.path.join(
            notebookParentDirectoryPath,
            rstFileName,
            )


        if os.path.exists(rstFilePath):
            if os.path.getmtime(rstFilePath) > os.path.getmtime(ipythonNotebookFilePath):
                return False

        self.runNBConvert(ipythonNotebookFilePath)
        with open(rstFilePath, 'r') as f:
            oldLines = f.read().splitlines()
        ipythonPromptPattern = re.compile('^In\[[\d ]+\]:')
        mangledInternalReference = re.compile(
            r'\:(class|ref|func|meth)\:\`\`?(.*?)\`\`?')
        newLines = ['.. _' + notebookFileNameWithoutExtension + ":"]
        currentLineNumber = 0
        while currentLineNumber < len(oldLines):
            currentLine = oldLines[currentLineNumber]
            # Remove all IPython prompts and the blank line that follows:
            if ipythonPromptPattern.match(currentLine) is not None:
                currentLineNumber += 2
                continue
            # Correct the image path in each ReST image directive:
            elif currentLine.startswith('.. image:: '):
                imageFileName = currentLine.partition('.. image:: ')[2]
                if '/' not in currentLine:
                    newImageDirective = '.. image:: {0}/{1}'.format(
                        imageFileDirectoryName,
                        imageFileName,
                        )
                    newLines.append(newImageDirective)
                else:
                    newLines.append(currentLine)
                currentLineNumber += 1
            elif "# ignore this" in currentLine:
                currentLineNumber += 2  #  # ignore this
                                        #  %load_ext music21.ipython21.ipExtension
            # Otherwise, nothing special to do, just add the line to our results:
            else:
                # fix cases of inline :class:`~music21.stream.Stream` being
                # converted by markdown to :class:``~music21.stream.Stream``
                newCurrentLine = mangledInternalReference.sub(
                    r':\1:`\2`',
                    currentLine
                    )
                newLines.append(newCurrentLine)
                currentLineNumber += 1

        # Guarantee a blank line after literal blocks.
        lines = [newLines[0]]
        for i, pair in enumerate(self.iterateSequencePairwise(newLines)):
            first, second = pair
            if len(first.strip()) \
                and first[0].isspace() \
                and len(second.strip()) \
                and not second[0].isspace():
                lines.append('')
            lines.append(second)
            if '.. parsed-literal::' in second:
                lines.append('   :class: ipython-result')

        with open(rstFilePath, 'w') as f:
            f.write('\n'.join(lines))

        return True

    def iterateSequencePairwise(self, sequence):
        prev = None
        for x in sequence:
            cur = x
            if prev is not None:
                yield prev, cur
            prev = cur

    def runNBConvert(self, ipythonNotebookFilePath):
#         import music21
        #runDirectoryPath = common.getBuildDocFilePath()
        from music21.ext.nbconvert import nbconvert_app as nb
        app = nb.NbConvertApp.instance()
        app.start(argv=['nbconvert', 'rst', ipythonNotebookFilePath])


## UNUSED
#     def processNotebook(self, ipythonNotebookFilePath):
#         from music21 import documentation # @UnresolvedImport
#         with open(ipythonNotebookFilePath, 'r') as f:
#             contents = f.read()
#             contentsAsJson = json.loads(contents)
#         directoryPath, unused_sep, baseName = ipythonNotebookFilePath.rpartition(
#             os.path.sep)
#         baseNameWithoutExtension = os.path.splitext(baseName)[0]
#         imageFilesDirectoryPath = os.path.join(
#             directoryPath,
#             '{0}_files'.format(baseNameWithoutExtension),
#             )
#         rstFilePath = os.path.join(
#             directoryPath,
#             '{0}.rst'.format(baseNameWithoutExtension),
#             )
#         lines, imageData = documentation.IPythonNotebookDocumenter(
#             contentsAsJson)()
#         rst = '\n'.join(lines)
#         self.write(rstFilePath, rst)
#         if not imageData:
#             return
#         if not os.path.exists(imageFilesDirectoryPath):
#             os.mkdir(imageFilesDirectoryPath)
#         for imageFileName, imageFileData in imageData.iteritems():
#             imageFilePath = os.path.join(
#                 imageFilesDirectoryPath,
#                 imageFileName,
#                 )
#             shouldOverwriteImage = True
#             with open(imageFilePath, 'rb') as f:
#                 oldImageFileData = f.read()
#                 if oldImageFileData == imageFileData:
#                     shouldOverwriteImage = False
#             if shouldOverwriteImage:
#                 with open(imageFilePath, 'wb') as f:
#                     f.write(imageFileData)


if __name__ == '__main__':
    import music21
    music21.mainTest()

