#!/usr/bin/env python3

import argparse, sys
from vcdvcd import VCDVCD
import subprocess, os
from tqdm import tqdm
import binascii
import logging
import logging.config

sections = []
section_mapping = {}
functions = []
graph_height = 1

# Logging
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('client')

def init_logging(verbose = True):
    """
    Create and set up Logger
    """
    loglevel = (logging.DEBUG if verbose else logging.INFO)
    logger.setLevel(loglevel)
    logger.info("Dot generator for vcd files")


def get_parser():
	parser = argparse.ArgumentParser(
		description='Visualize the program trace of a VCD waveform as a dot graph.',
	)
	parser.add_argument(
		'-f',
		dest='file',
		help='the VCD file to parse',
	)
	parser.add_argument(
		'-e',
		dest='elffile',
		help='the elf file to parse',
	)
	parser.add_argument(
		'-o',
		dest='outfile',
		help='the out file to generate',
	)

	return parser.parse_args()

def calculate_section_order(elf_path):
	# First, get text sections
	proc = subprocess.run(['readelf', '-S', elf_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

	if proc.returncode == 0:
		lines = proc.stdout.split('\n')

		for l in lines:
			if ".text" in l:
				l = l[l.index("]"):]
				values = list(filter("".__ne__,l.split(" ")))

				sections.append({"name": values[1], "start": int(values[3], 16), "size":int(values[5],16), "end":int(values[3],16)+int(values[5],16), "functions":[]})

	# Next, get all functions and assign them to one section

	proc = subprocess.run(['nm', '-C', '--defined-only', elf_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

	if proc.returncode == 0:
		lines = proc.stdout.split('\n')
		for l in lines:
			values = list(filter("".__ne__,l.split(" ")))
			if not values:
				continue
			addr = int(values[0], 16)

			func_addr_index = addr >> 1
			func = values[2]

			# Expand list if there is no space
			if len(functions) - 1 < func_addr_index :
				functions.extend((func_addr_index - len(functions) + 1) * [None])
			functions[func_addr_index] = func

			for s in sections:
				if s["start"] <= addr and s["end"] > addr:
					s["functions"].append(func)
					break #no need to go on with loop

	# now loop over functions and fill in the gaps with the initial value
	prev_func = None
	for i in tqdm(range(len(functions))):
		if functions[i] is None:
			functions[i] = prev_func
		else:
			prev_func = functions[i]

	column_count = 1
	for s in sections:
		s["col_offset"] = column_count
		column_count = column_count + len(s["functions"]) + 1
	logger.debug(sections)

	return column_count

		
def prepare_dot_graph():
	s = "digraph g{\n" \
		+ "// graph [ bgcolor=lightgray]\n" \
		+ "node [style=filled fillcolor=\"white\"]\n"\
		+ "0 [style=invis pos=\"0,0!\"]\n\n"
	cluster_names = 0
	for sec in sections:
		s = s \
		+ "subgraph cluster_{0}".format(cluster_names) + " {\n" \
		+ "label=\"{0}\"\n".format(sec["name"]) \
		+ "bb=\"{0},{1},{2},{3}\"\n".format(sec["col_offset"], 0, len(sec["functions"]), -graph_height) \
		+ "bgcolor=lightgray\n" \
		+ "n{0}_1 [style=invis pos=\"{1},{2}!\"]\n".format(cluster_names, sec["col_offset"], 0)\
		+ "n{0}_2 [style=invis pos=\"{1},{2}!\"]\n".format(cluster_names, sec["col_offset"] + len(sec["functions"]), -graph_height)\
		+ "}\n\n"
		cluster_names = cluster_names + 1
	return s

def finish_dot_graph():
	s = "}"
	return s

def dot_string_function(prev_node, func_name, time_val, trace_index):
	s = time_val + " [pos=\"" + str(section_mapping[func_name]) + "," + str(-trace_index) + "!\" label=\"" + func_name + "\"]\n"
	s = s + prev_node + " -> " + time_val + "\n"
	return s

def convert_inst(t):
	return [t[0],''.join(chr(int(t[1][i:i+8], 2)) for i in range(0, len(t[1]), 8)).replace('\x00','')]


"""
Checks whether we ignore the given function name. This list is targeted for Riot
"""
ignored_functions = ["putchar", "uart_write_byte", "vuprintf", "print_field", "vprintf", "__udivhi3", "__umodhi3"]
def is_ignored(func_name):
	if func_name in ignored_functions:
		return True
	return False


if __name__ == '__main__':
	args = get_parser()

	init_logging(verbose=False)

	# Do the parsing.
	logger.info("Parsing vcd file..")
	vcd = VCDVCD(args.file)
	if vcd is None:
		print("File error\n")
		sys.exit(-1)
	logger.info("Parsed VCD file")

	signal_pc = vcd['TOP.tb_openMSP430.inst_pc[15:0]']
	pc_values = list(map(lambda x : [x[0], hex(int(x[1],2))], signal_pc.tv))
	signal_inst = vcd['TOP.tb_openMSP430.inst_full[255:0]']
	inst_values = list(map(convert_inst, signal_inst.tv))


	res = []
	prev_val = ""
	inst_counter = 0
	inst_time = signal_pc.tv[0][0]
	prev_function_time = "0"
	prev_function_name = ""

	dot_strings = []

	column_count = calculate_section_order(args.elffile)

	logger.info("Done with setup. Parsing through the vcd file now...")

	for i in tqdm(range(len(signal_pc.tv))):	
		val = [pc_values[i][0], pc_values[i][1]]
		# only move to the next item in inst list if timestamps map.
		if inst_values[inst_counter][0] == pc_values[i][0]:
			prev_val = inst_values[inst_counter][1]
			inst_counter = inst_counter + 1
		val.append(prev_val)
	
		output = functions[int(val[1], 16) >> 1]

		val.append(output)
		if output != prev_function_name and not is_ignored(output):
			if output not in section_mapping:
				for s in sections:
					done = False
					if output in s["functions"]:
						section_mapping[output] = s["functions"].index(output) + s["col_offset"]
						done = True
						break
				if not done:
					logger.warning("Warning: " + output + " was not found in sections! Appending it manually (it may look misplaced though)")
					section_mapping[output] = column_count
					column_count = column_count + 1
				
			dot_strings.append(dot_string_function(prev_function_time, output, str(pc_values[i][0]), graph_height))
			prev_function_time = str(pc_values[i][0])
			prev_function_name = output
			graph_height = graph_height + 1


		# add line to instructions
		res.append(val)

	logger.info("Done with reading from the VCD file. Writing to dot file...")

	# Wrap up and close file
	dot_file = open(args.outfile, "w")
	dot_file.write(prepare_dot_graph())
	for s in tqdm(dot_strings):
		dot_file.write(s)
	dot_file.write(finish_dot_graph())
	dot_file.close()

	logger.info("Success. Exiting")
	sys.exit(0)