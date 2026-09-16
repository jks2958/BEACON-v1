# Phase 3 Feature Reproduction Result

## Reference-pair search

No paired raw `.pcap`/`.pcapng` and corresponding prepared Network feature CSV
exists in the repository. The committed Network data consists of trained
artifacts and metrics; the raw `NetCSVs` are explicitly not distributed. The
training loader consumes files already named `*_traffic_cleaned.pcap.csv`, but
no code that produced those CSVs is present.

No reference pair was fabricated.

## Results

| Outcome | Features |
|---|---:|
| Exact empirical match | 0 |
| Match within justified tolerance | 0 |
| Diagnostic fields computed, semantics still unverified | 20 |
| Not emitted by the diagnostic extractor | 322 |
| Safe for production inference | 0 |

The dependency-free parser successfully reads classic PCAP and PCAPNG Enhanced
Packet Blocks with Ethernet/IPv4 TCP or UDP traffic. It groups bidirectional
flows and exposes 20 conservative packet facts for diagnostics. These values
are not claimed to reproduce the original extractor.

## Blocking semantics

The 342-column model contract includes extensive active/idle, bulk, handshake,
subflow, inter-arrival, directional delta, distribution-mode, skewness, and
covariance features. Exact definitions depend on such details as flow timeout,
packet direction, header accounting, population/sample variance conventions,
mode tie-breaking, bulk thresholds, and incomplete-handshake encoding. Those
semantics cannot be recovered reliably from column names alone.

## Gate decision

**Native PCAP/PCAPNG production inference is not enabled.** Parsed captures are
marked partially compatible and `analyze_evidence()` fails closed before the
Network controller. Enabling inference requires a paired reference corpus or
the original feature-extraction implementation and feature-by-feature
reproduction tests.
