# vcd-tracer

This is a program trace graph generator based on vcd files. Use an elf and vcd file as input, and this tool generates a GraphViz DOT file that can be viewed with (hopefully) any dot viewer as long as the engine `neato` or `fdp` are used. I tested this with `xdot` (e.g. installable via `apt get`).

Note that the mapping of functions to addresses is mostly targeted at Sancus or at the very least targeted at MSP-430 right now. To retrieve a function address in O(1), the script pre-generates a list of all addresses and the function that precedes each address. Good luck doing that on anything above 16-bit architectures.

## Example

```bash
$ ./generate_trace_graph.py -f examples/sancus-arithmetic/sim.vcd -e examples/sancus-arithmetic/main.elf -o examples/sancus-arithmetic/trace.dot
22.10.2021_12:10:09-client_INFO: Dot generator for vcd files
22.10.2021_12:10:09-client_INFO: Parsing vcd file..
22.10.2021_12:10:57-client_INFO: Parsed VCD file
100%|████████████████████████████████| 32769/32769 [00:00<00:00, 1217690.37it/s]
22.10.2021_12:10:58-client_INFO: Done with setup. Parsing through the vcd file now...
  0%|                                                 | 0/30725 [00:00<?, ?it/s]22.10.2021_12:10:58-client_WARNING: Warning: __sm_foo_num_inputs was not found in sections! Appending it manually (it may look misplaced though)
100%|█████████████████████████████████| 30725/30725 [00:00<00:00, 495909.39it/s]
22.10.2021_12:10:58-client_INFO: Done with reading from the VCD file. Writing to dot file...
100%|█████████████████████████████████████| 121/121 [00:00<00:00, 727092.81it/s]
22.10.2021_12:10:58-client_INFO: Success. Exiting
$ xdot examples/sancus-arithmetic/trace.dot -f neato
```
