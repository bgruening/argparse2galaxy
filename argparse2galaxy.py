#!/usr/bin/env python

import os
import sys
import argparse
from xml.dom.minidom import Document

class Tool():

    def __init__( self, ap_parser, **kwargs ):
        self.ap_parser = ap_parser
        self.name = parser.prog
        self.id = parser.prog
        self.version = kwargs.get('version', None) or str(parser.version) or '0.1'
        self.description = kwargs.get('version', None) or parser.description or 'Insert Short Description'
        self.blacklisted_parameters = ['--version', '--verbose', '--help']


    def parse( self ):
        self.doc = Document( )
        self.tool = self.create_tool( )
        self.create_description( )
        self.create_requirements( )
        self.create_stdio( )
        self.doc.appendChild( self.tool )
        self.create_command( )
        self.create_inputs( )
        self.create_outputs( )
        self.create_help( )
        self.create_reference()


    def convert_to_galaxy( self ):
        self.doc.writexml(sys.stdout, indent="    ", addindent="    ", newl='\n', encoding="UTF-8")


    def create_tool( self ):
        tool = self.doc.createElement("tool")
        tool.setAttribute( "id", self.name )
        tool.setAttribute( "version", self.version )
        tool.setAttribute( "name", self.name )
        return tool


    def create_description( self ):
        description_node = self.doc.createElement("description")
        description = self.doc.createTextNode( self.description )
        description_node.appendChild( description )
        self.tool.appendChild( description_node )


    def get_param_name( self, param ):
        long_param = self.get_longest_param_name( param )
        return long_param.replace('-', '_').strip('_')


    def get_longest_param_name( self, param ):
        if len( param.option_strings ) == 1:
            return param.option_strings[0]
        else:
            if len( param.option_strings[0] ) > len( param.option_strings[1] ):
                return param.option_strings[0]
            else:
                return param.option_strings[1]


    def get_param_type( self, param ):
        if type(param) in [argparse._StoreTrueAction, argparse._StoreFalseAction]:
            return 'boolean'
        elif type(param) == argparse._StoreAction:

            if param.choices is not None:
                return 'select'
            if param.type == int:
                return 'integer'
            elif param.type == float:
                return 'float'
        return 'text'


    def is_blacklisted( self, param ):
        for name in param.option_strings:
            if name in self.blacklisted_parameters:
                return True
        return False


    def create_command( self ):
        final_command = self.name + '\n'

        for param in self.extract_parameters( ):
            command = ''
            param_name = self.get_param_name( param )
            param_type = self.get_param_type( param )

            if self.is_blacklisted( param ):
                    continue

            if param_type == 'boolean':
                command += '$%s\n' %  ( param_name )
            else:

                if param_type == 'text':
                    command += "\n#if str($%(param_name)s).strip() != '':\n    "  % {"param_name": param_name}

                command = "%s '${%s}'\n" % (self.get_longest_param_name( param ), param_name)
                if param_type == 'text':
                    command += "#end if\n"

            final_command += command

        command_node = self.doc.createElement("command")
        command_text_node = self.doc.createCDATASection( final_command.strip() )
        command_node.appendChild(command_text_node)
        self.tool.appendChild(command_node)


    def create_inputs( self ):
        inputs_node = self.doc.createElement("inputs")

        collect_inputs = list()

        for param in self.extract_parameters( ):
            if self.is_blacklisted( param ):
                continue
            inputs_node.appendChild( self.create_param_node( param ) )

        self.tool.appendChild(inputs_node)


    def extract_parameters( self ):
        """
            ToDo: Add some parameter filtering here and react on nested parameters
        """
        parameters = []
        for parameter in self.ap_parser._actions:
            yield parameter


    def create_param_node( self, param ):

        param_name = self.get_param_name( param )
        param_type = self.get_param_type( param )

        param_node = self.doc.createElement( "param" )
        param_node.setAttribute( "name", param_name )
        label = ""
        if param.help is not None:
            label = param.help
        else:
            label = "%s parameter" % self.get_longest_param_name( param )
        param_node.setAttribute("label", label)
        param_node.setAttribute("help", "(%s)" % self.get_longest_param_name( param ))

        if param_type is None:
            raise "Unrecognized parameter type '%(type)' for parameter '%(name)'" % {"type":param_type, "name":param_name}

        param_node.setAttribute("type", param_type)
        if param.required:
            param_node.setAttribute("optional", str(not param.required))

        # check for parameters with restricted values (which will correspond to a "select" in galaxy)
        if param_type == 'select':
            for choice in param.choices:
                option_node = self.doc.createElement( "option" )
                option_node.setAttribute( "value", str(choice) )
                option_label = self.doc.createTextNode( str(choice) )
                option_node.appendChild( option_label )
                param_node.appendChild( option_node )
            return param_node

        if param_type == "text":
            # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
            param_node.setAttribute("size", "20")

        if param_type == 'boolean':
            if type(param) == argparse._StoreTrueAction:
                param_node.setAttribute("truevalue", "%s" % self.get_longest_param_name( param ))
                param_node.setAttribute("falsevalue", '')
            elif type(param) == argparse._StoreFalseAction:
                param_node.setAttribute("falsevalue", "%s" % self.get_longest_param_name( param ))
                param_node.setAttribute("truevalue", '')

            param_node.setAttribute("checked", str(param.default))

        # check for default value
        if param.default is not None:
            if param_type != "boolean":
                param_node.setAttribute("value", str(param.default))
        else:
            param_node.setAttribute("value", '')

        return param_node


    def create_outputs( self ):
        """
            How to guess the output parameters, usualy they are not of type FILE
            whitelist?
        """
        outputs_node = self.doc.createElement("outputs")
        outputs_node.appendChild( self.create_data_node( ) )
        self.tool.appendChild(outputs_node) 

    def create_data_node( self ):
        data_node = self.doc.createElement("data")
        data_node.setAttribute("name", 'outfile')
        data_node.setAttribute("format", 'data')
        
        data_node.setAttribute("label", '${tool.name} on ${on_string}')
        data_node.appendChild( self.create_filter_node() )
        data_node.appendChild( self.create_change_format_node() )
        return data_node

    def create_filter_node( self, data_format = 'EXAMPL'):
        """
            <filter>'bam' in outputs</filter>
        """
        filter_node = self.doc.createElement("filter")
        option_label = self.doc.createTextNode("'%s' in param_out_type" % (data_format))
        filter_node.appendChild(option_label)
        return filter_node

    def create_change_format_node( self, data_formats = ['foo', 'bar'], input_ref = 'infile'):
        """
            <change_format>
                <when input="secondary_structure" value="true" format="text"/>
            </change_format>
        """
        change_format_node = self.doc.createElement("change_format")
        for data_format in data_formats:
            when_node = self.doc.createElement("when")
            when_node.setAttribute('input', input_ref)
            when_node.setAttribute('value', data_format)
            when_node.setAttribute('format', data_format)
            change_format_node.appendChild( when_node )
        return change_format_node


    def create_requirements( self ):
        """
        <requirements>
            <requirement type="binary">@EXECUTABLE@</requirement>
            <requirement type="package" version="1.1.1">TODO</requirement>
        </requirements>
        """
        requirements_node = self.doc.createElement("requirements")

        requirement_node = self.doc.createElement("requirement")
        requirement_node.setAttribute("type", "binary")
        requirement_text_node = self.doc.createTextNode('@EXECUTABLE@')
        requirement_node.appendChild(requirement_text_node)
        requirements_node.appendChild(requirement_node)

        requirement_node = self.doc.createElement("requirement")
        requirement_node.setAttribute("type", "package")
        requirement_node.setAttribute("version", "1.1.1")
        requirement_text_node = self.doc.createTextNode('TODO')
        requirement_node.appendChild(requirement_text_node)
        requirements_node.appendChild(requirement_node)
        self.tool.appendChild( requirements_node )


    def create_reference( self ):
        """
            <citations>
                <citation type="doi">10.1371/journal.pcbi.1003153</citation>
            </citations>
        """
        citations_node = self.doc.createElement("citations")
        citation_node = self.doc.createElement("citation")
        citation_node.setAttribute( "type", "doi" )
        citation_text_node = self.doc.createTextNode('10.1371/journal.pcbi.1003153')
        citation_node.appendChild(citation_text_node)
        citations_node.appendChild( citation_node )
        self.tool.appendChild( citations_node )


    def create_stdio( self ):
        """
            <!-- Anything other than zero is an error -->
            <exit_code range="1:" />
            <exit_code range=":-1" />
            <!-- In case the return code has not been set propery check stderr too -->
            <regex match="Error:" />
            <regex match="Exception:" />
        """
        stdio_node = self.doc.createElement("stdio")
        exit_code_node = self.doc.createElement("exit_code")
        exit_code_node.setAttribute("range", "1:")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = self.doc.createElement("exit_code")
        exit_code_node.setAttribute("range", ":-1")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = self.doc.createElement("regex")
        exit_code_node.setAttribute("match", "Error:")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = self.doc.createElement("regex")
        exit_code_node.setAttribute("match", "Exception:")
        stdio_node.appendChild(exit_code_node)
        self.tool.appendChild( stdio_node)


    def create_help( self ):
        """
            **What it does**
            + some help from the argparse definitions
        """
        help_text = '**What it does**\n\n'
        help_text += self.ap_parser.description or ' Insert Short Description'
        help_text += '\n'
        help_text += self.ap_parser.epilog or 'Isert long description with website link'
        help_text += '\n'
        help_text += self.ap_parser.format_help() or 'insert help instructions'
        help_text += '\n'
        help_text += self.ap_parser.format_usage()
        help_text += '\n'

        help_node = self.doc.createElement("help")
        help_text_node = self.doc.createCDATASection( help_text )
        help_node.appendChild( help_text_node )
        self.tool.appendChild(help_node)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.version = 3.4
    # Exaple parser from the platypus code and additional tests
    parser.add_argument("-o", "--output", dest="output", help="Output SNP data file", default="AllVariants.vcf")
    parser.add_argument("--refFile",dest="refFile", help="Fasta file of reference. Index must be in same directory", required=True)
    parser.add_argument("--skipRegionsFile", dest="skipRegionsFile",  help = "region as comma-separated list of chr:start-end, or just list of chr, or nothing", default=None)
    parser.add_argument("--bufferSize", dest="bufferSize", type=int, help = "Data will be buffered in regions of this size", default=100000, required=False)
    parser.add_argument("--minReads", dest="minReads", help="Minimum number of supporting reads required before a variant candidate will be considered.", type=int, default=2)
    parser.add_argument("--verbosity", dest="verbosity", help="Level of logging", type=int, default=2)
    parser.add_argument("--printAlignments", dest="printAlignments", help="If 1, then alignments of reads to haplotypes will be printed to the log file", type=int, default=0)
    parser.add_argument("--maxReadLength", dest="rlen", help="Maximum read length", type=int, default=100)
    parser.add_argument("--logFileName", dest="logFileName", help="Name of log file", default="log.txt")
    parser.add_argument("--nCPU", dest="nCPU", help="Number of processors to use", type=int, default=1)
    parser.add_argument("--parseNCBI", dest="parseNCBI", help="", type=int, default=0)
    parser.add_argument('--door', type=int, choices=range(1, 4))
    parser.add_argument('--floor', choices=['dance', 'rock', 'pop', 'metal'], help='baz help')
    parser.add_argument('--true-feature', dest='feature', action='store_true')
    parser.add_argument('--false-feature', dest='feature', action='store_false')


    tool = Tool( parser )
    tool.parse()
    tool.convert_to_galaxy()
