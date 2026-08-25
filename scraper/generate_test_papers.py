#!/usr/bin/env python3
"""
Procedural IEEE Test Paper Generator
Generates N (default: 30) diverse IEEE-formatted PDF papers with widely varying sizes:
- Abstract lengths from ~40 words (short) to ~320 words (very long)
- Title lengths from 4 words to 22 words
- Author counts from 1 to 6 with single or multiple university affiliations
- Keywords from 4 to 9 terms

Usage:
    python3 generate_test_papers.py [count] [output_folder]
    e.g. python3 generate_test_papers.py 30 IncompletePDF
"""

import os
import sys
import random
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# ── Procedural Data Dictionaries ──

DOMAINS = [
    ("Autonomous Electric Mobility", "Solid-State Battery Management", "V2X Telemetry"),
    ("Genomic Sequencing Informatics", "CRISPR-Cas9 Off-Target Analysis", "Epigenetic Modeling"),
    ("Deep-Space Optical Telemetry", "CubeSat Laser Mesh Networks", "Attitude Determination"),
    ("Neuromorphic Computing", "Spiking Neural Circuits", "Memristive Synaptic Arrays"),
    ("Sustainable Green Hydrogen", "Electrolyzer Cell Efficiency", "Microgrid Load Balancing"),
    ("Quantum Photonics", "Continuous-Variable QKD", "Photonic Qubit Transduction"),
    ("Smart Precision Agritech", "Multispectral Canopy Profiling", "Autonomous Crop Robotics"),
    ("Advanced Robotic Surgery", "Sub-Millimeter Motion Scaling", "Haptic Teleoperation"),
    ("Zero-Knowledge Cryptography", "zk-SNARK Rollups", "Cross-Chain Liquidity Bridges"),
    ("Hypersonic Aerodynamics", "Plasma Flow Actuation", "Boundary Layer Stability"),
    ("Multimodal Edge Intelligence", "Sparse Mixture-of-Experts", "Speculative Decoder Gating"),
    ("Wearable Biosensing Devices", "Photoplethysmography De-noising", "Bio-impedance Spectroscopy")
]

FIRST_NAMES = [
    "Aarav", "Priyanka", "Tejaswi", "Suresh", "Kailash", "Garima", "Siddharth",
    "Vivek", "Rashmi", "Tapan", "Arpit", "Praveen", "Mitesh", "Sanyog", "Ananya",
    "Vikramaditya", "Rajeshwari", "Alok", "Meenakshi", "Sunita", "Rohan", "Divya",
    "Kavita", "Aditya", "Neha", "Nikhil", "Isha", "Manish", "Shweta", "Harish",
    "Tanvi", "Abhinav", "Devanshi", "Tarun", "Karan", "Pooja", "Aayush", "Gaurav"
]

LAST_NAMES = [
    "Sharma", "Singh", "Palisetti", "Jain", "Bandhu", "Mathur", "Parihar",
    "Gupta", "Jangid", "Nahar", "Rawat", "Solanki", "Roy", "Sen", "Swaminathan",
    "Nath", "Sundaram", "Deshmukh", "Verma", "Chopra", "Reddy", "Patel",
    "Bose", "Menon", "Mukherjee", "Iyer", "Rao", "Dubey", "Mehta", "Bhat",
    "Chakraborty", "Sengupta", "Kulkarni", "Bhattacharya", "Agarwal", "Mishra"
]

DEPARTMENTS = [
    "Department of Computer Science and Engineering",
    "Department of Aerospace and Astronautical Engineering",
    "Department of Biotechnology and Genetic Engineering",
    "Department of Electrical and Energy Systems Engineering",
    "School of Artificial Intelligence and Data Science",
    "Center for Computational Biology and Genomic Informatics",
    "Department of Cyber Security and Applied Cryptography",
    "Department of Quantum Physics and Nanophotonics",
    "School of Robotics and Autonomous Mechatronics"
]

INSTITUTIONS = [
    "Indian Institute of Technology Bombay, Powai, Mumbai, India",
    "Indian Institute of Technology Delhi, Hauz Khas, New Delhi, India",
    "Indian Institute of Science, Bengaluru, Karnataka, India",
    "Manipal Academy of Higher Education, Manipal, Karnataka, India",
    "Sagar Institute of Science and Technology, Bhopal, Madhya Pradesh, India",
    "Birla Institute of Technology and Science, Pilani, Rajasthan, India",
    "National Institute of Technology Karnataka, Surathkal, Mangalore, India",
    "All India Institute of Medical Sciences, New Delhi, India",
    "Amrita Vishwa Vidyapeetham, Coimbatore, Tamil Nadu, India",
    "Medicaps University, A.B. Road, Indore, Madhya Pradesh, India"
]

TITLE_TEMPLATES_SHORT = [
    "{method} for {domain} Systems",
    "Design of {method} in {domain}",
    "{metric} Analysis of {domain} Networks",
    "Secure {method} Protocols for {domain}",
    "High-Performance {method} in {domain}",
]

TITLE_TEMPLATES_MEDIUM = [
    "A Novel {method} Architecture for High-Throughput {domain} Applications",
    "Empirical Evaluation of {method} and {secondary} in Heterogeneous {domain}",
    "Optimizing {metric} in Distributed {domain} via Adaptive {method}",
    "Fault-Tolerant {method} Frameworks for Next-Generation {domain}",
    "A Scalable {method} Pipeline for Real-Time {domain} Diagnostics",
]

TITLE_TEMPLATES_LONG = [
    "Comprehensive Benchmarking of {method} and {secondary} Architectures for Real-Time {domain} and Diagnostic Optimization",
    "Autonomous Threat Mitigation and Dynamic Resource Allocation in Large-Scale {domain} via Multi-Agent {method} Ensembles",
    "Hierarchical Optimization of Energy Efficiency and {metric} in Dense {domain} using Physics-Informed {method}",
    "High-Precision Synthesis of {method} and {secondary} for Ultra-Low-Latency {domain} Infrastructure",
]

METHODS = [
    "Neural Beamforming", "Federated Gradient Compression", "Graph Neural Network", "Quantum Key Encapsulation",
    "Transformer Diffusion", "Reinforcement Learning", "Gradient Sparsification", "Consensus Protocol",
    "Micro-Telemetry", "Topological Feature Extraction", "Lattice Cryptography", "Dynamic Cache Sharding",
    "Spiking Synaptic Plasticity", "Sparse Mixture-of-Experts", "zk-SNARK Verification", "Wavelet Denoising"
]

SECONDARIES = [
    "Wavelet Reconstruction", "Attention Mechanisms", "Momentum Caching", "Edge Ensembles",
    "Probabilistic Reasoning", "Zero-Knowledge Proofs", "Non-IID Clustering", "Temporal Gating",
    "Low-Rank Adaptation", "Specular Reflection Suppression", "Self-Supervised Contrastive Losses"
]

METRICS = [
    "Latency and Throughput", "Energy Efficiency", "Convergence Rate", "Spectral Purity",
    "Fault Tolerance", "Reconstruction Fidelity", "Computational Complexity", "Resilience",
    "Thermodynamic Efficiency", "Signal-to-Noise Ratio"
]

ABSTRACT_SENTENCES_OPENING = [
    "Recent advancements in {domain} have created unprecedented opportunities and urgent operational demands for scalable, low-latency computational frameworks in distributed cyber-physical ecosystems.",
    "Large-scale deployments of modern {domain} systems frequently encounter severe communication bottlenecks, computational stragglers, and non-stationary stochastic data drifts that hinder overall convergence.",
    "Ensuring high-fidelity operation, cryptographic resilience, and energy efficiency in resource-constrained {domain} remains a fundamental open challenge across applied academic and industrial engineering.",
    "Next-generation {domain} architectures necessitate adaptive optimization methods that respond seamlessly to dynamic operational conditions, bursty workloads, and unpredictable telemetry interruptions.",
    "The exponential growth of high-frequency telemetry streams in modern {domain} calls for resilient, decentralized algorithmic paradigms capable of real-time parameter synthesis and error mitigation.",
    "Deploying robust autonomy within {domain} demands ultra-reliable communication links and compute-efficient algorithmic accelerators capable of operating under strict thermal and power limits."
]

ABSTRACT_SENTENCES_PROPOSAL = [
    "In this study, we propose a novel {method} framework deeply integrated with {secondary} to address critical trade-offs between {metric} and computational overhead.",
    "We introduce an end-to-end algorithmic pipeline that utilizes {method} for real-time parameter tuning, robust anomaly suppression, and distributed load balancing.",
    "To overcome these pervasive limitations, we design a hierarchical {method} model that adaptively balances local computing budgets against global transmission costs.",
    "Our approach synthesizes multi-layer {method} representations with localized {secondary} techniques to maximize overall operational reliability and throughput.",
    "We establish a theoretical formulation and an empirical prototype utilizing specialized {method} modules tailored for heterogeneous embedded hardware nodes.",
    "This work presents a lightweight, hardware-accelerated {method} implementation that dynamically adapts to channel volatility and compute constraints."
]

ABSTRACT_SENTENCES_DETAILS = [
    "The proposed scheme incorporates localized momentum filtering, reducing gradient divergence across non-stationary input distributions by up to 42% under rigorous benchmark conditions.",
    "By decoupling the spatial feature extractors from temporal sequence decoders, our system achieves sub-millisecond inference throughput without sacrificing reconstruction precision.",
    "Extensive hardware simulations illustrate that dynamic quantization enables a 3.4x reduction in total memory footprint across resource-constrained edge hardware testbeds.",
    "Furthermore, cryptographic integrity is preserved through lightweight verification mechanisms that prevent adversarial injection and coordinated zero-day sensor spoofing vectors.",
    "The underlying mathematical formulations establish rigorous convergence bounds and asymptotic stability guarantees under both convex and non-convex optimization constraints.",
    "We also incorporate self-supervised regularization and adaptive loss weighting to mitigate overfitting on sparse, irregularly sampled sensor telemetry streams.",
    "A distributed state-synchronization protocol is introduced to maintain transactional atomicity across asynchronous nodes during intermittent channel blackouts.",
    "In addition, localized gradient compression algorithms are leveraged to minimize peak inter-node bandwidth utilization while retaining gradient fidelity across iterations.",
    "The system architecture employs dynamic runtime profiling to adjust neural quantization levels on-the-fly, ensuring optimal thermal efficiency on battery-powered edge devices.",
    "We formalize a game-theoretic resource scheduler that prevents node starvation and optimizes collective utility functions across heterogeneous edge clusters."
]

ABSTRACT_SENTENCES_RESULTS = [
    "Comprehensive empirical evaluations across four public benchmark datasets demonstrate a 31.8% improvement in {metric} compared to legacy state-of-the-art baselines.",
    "Experimental results on high-throughput testbeds confirm that our framework sustains greater than 98.4% accuracy while curtailing end-to-end latency by 2.6x.",
    "Field trials in production-grade environments validate that the proposed solution delivers substantial energy savings with zero degradation in service quality or system responsiveness.",
    "Comparative ablation analyses demonstrate consistent superiority over existing baseline architectures under widely varying signal-to-noise ratios and bursty traffic patterns.",
    "The resulting implementation provides an open-source, fully reproducible baseline for future industrial deployments and academic explorations in {domain}."
]

KEYWORDS_POOL = [
    "Machine Learning", "Neural Networks", "Deep Learning", "Edge Computing", "IoT Networks",
    "Optimization", "Signal Processing", "Cybersecurity", "Blockchain", "Quantum Key Distribution",
    "Federated Learning", "Graph Neural Networks", "Transformers", "Computer Vision", "Real-Time Telemetry",
    "Fault Tolerance", "Embedded Systems", "Resource Allocation", "Energy Efficiency", "Anomaly Detection",
    "Autonomous Robotics", "Bio-impedance", "Genomic Sequencing", "Battery Management", "Plasma Actuation"
]


def generate_random_paper_content(index):
    domain_tup = random.choice(DOMAINS)
    domain = domain_tup[0]
    sub_domain = domain_tup[1]
    method = random.choice(METHODS)
    secondary = random.choice(SECONDARIES)
    metric = random.choice(METRICS)

    # ── 1. Title Generation (Short, Medium, or Long) ──
    title_category = random.choices(['short', 'medium', 'long'], weights=[0.25, 0.50, 0.25])[0]
    if title_category == 'short':
        tmpl = random.choice(TITLE_TEMPLATES_SHORT)
    elif title_category == 'medium':
        tmpl = random.choice(TITLE_TEMPLATES_MEDIUM)
    else:
        tmpl = random.choice(TITLE_TEMPLATES_LONG)

    title = tmpl.format(domain=domain, method=method, secondary=secondary, metric=metric)

    # ── 2. Author & Affiliation Generation (1 to 6 authors) ──
    num_authors = random.choices([1, 2, 3, 4, 5, 6], weights=[0.15, 0.25, 0.30, 0.15, 0.10, 0.05])[0]
    author_names = []
    used_first = random.sample(FIRST_NAMES, num_authors)
    used_last = random.sample(LAST_NAMES, num_authors)
    for i in range(num_authors):
        prefix = "Dr. " if random.random() < 0.25 else ("Prof. " if random.random() < 0.15 else "")
        author_names.append(f"{prefix}{used_first[i]} {used_last[i]}")

    authors_str = ", ".join(author_names)

    num_affils = 1 if num_authors <= 2 else (random.choice([1, 2]) if num_authors <= 4 else random.choice([2, 3]))
    affil_list = []
    chosen_insts = random.sample(INSTITUTIONS, num_affils)
    chosen_depts = random.sample(DEPARTMENTS, num_affils)
    for d, inst in zip(chosen_depts, chosen_insts):
        affil_list.append(f"{d}, {inst}")
    affiliations_str = "; ".join(affil_list)

    # ── 3. Abstract Generation (Short ~45-60w, Medium ~120-160w, Long ~200-240w, Very Long ~280-330w) ──
    abstract_category = random.choices(['short', 'medium', 'long', 'very_long'], weights=[0.25, 0.35, 0.25, 0.15])[0]

    opening = random.choice(ABSTRACT_SENTENCES_OPENING).format(domain=domain, method=method)
    proposal = random.choice(ABSTRACT_SENTENCES_PROPOSAL).format(domain=domain, method=method, secondary=secondary, metric=metric)
    results = random.choice(ABSTRACT_SENTENCES_RESULTS).format(domain=domain, method=method, metric=metric)

    if abstract_category == 'short':
        # ~45-60 words
        abstract = f"{opening} {proposal}"
    elif abstract_category == 'medium':
        # ~120-160 words
        details = random.sample(ABSTRACT_SENTENCES_DETAILS, 3)
        abstract = f"{opening} {proposal} {' '.join(details)} {results}"
    elif abstract_category == 'long':
        # ~200-240 words
        details = random.sample(ABSTRACT_SENTENCES_DETAILS, 6)
        abstract = f"{opening} {proposal} {' '.join(details)} {results}"
    else:  # very_long
        # ~280-330 words
        details = random.sample(ABSTRACT_SENTENCES_DETAILS, 9)
        extra_open = random.choice([s for s in ABSTRACT_SENTENCES_OPENING if s != opening]).format(domain=sub_domain, method=method)
        extra_res = random.choice([s for s in ABSTRACT_SENTENCES_RESULTS if s != results]).format(domain=domain, method=method, metric=metric)
        abstract = f"{opening} {extra_open} {proposal} {' '.join(details)} {results} {extra_res}"

    word_count = len(abstract.split())

    # ── 4. Keywords Generation (4 to 9 terms) ──
    num_kw = random.randint(4, 8)
    chosen_kw = [domain, method] + random.sample([k for k in KEYWORDS_POOL if k not in (domain, method)], num_kw - 2)
    keywords_str = ", ".join(chosen_kw)

    return {
        'title': title,
        'authors': authors_str,
        'affiliations': affiliations_str,
        'abstract': abstract,
        'keywords': keywords_str,
        'word_count': word_count,
        'category': abstract_category
    }


def create_ieee_test_pdf(filename, data):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    st_title = ParagraphStyle(
        'IEEE_Title',
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    st_auth = ParagraphStyle(
        'IEEE_Authors',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=4
    )

    st_aff = ParagraphStyle(
        'IEEE_Affiliations',
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=14
    )

    st_abs = ParagraphStyle(
        'IEEE_Abstract',
        fontName='Times-Roman',
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )

    st_kw = ParagraphStyle(
        'IEEE_Keywords',
        fontName='Times-Italic',
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=16
    )

    st_body = ParagraphStyle(
        'IEEE_Body',
        fontName='Times-Roman',
        fontSize=10,
        leading=13,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )

    story = [
        Paragraph(data['title'], st_title),
        Paragraph(data['authors'], st_auth),
    ]
    if data['affiliations']:
        story.append(Paragraph(data['affiliations'], st_aff))

    story.extend([
        Paragraph(f"<b>Abstract— </b>{data['abstract']}", st_abs),
        Paragraph(f"<b>Keywords— </b><i>{data['keywords']}</i>", st_kw),
        Spacer(1, 10),
        Paragraph("<b>I. INTRODUCTION</b>", ParagraphStyle('H1', fontName='Times-Bold', fontSize=10, leading=13)),
        Paragraph("With recent advancements in distributed computing and edge intelligent systems, modern telemetry architectures demand highly resilient, latency-sensitive pipelines that guarantee throughput under stringent bandwidth constraints.", st_body),
        Paragraph("This study analyzes the performance benchmarks, empirical verifications, and architectural trade-offs observed during experimental trials.", st_body)
    ])

    doc.build(story)


def main():
    # Parse count and output folder
    count = 30
    target_folder = "IncompletePDF"

    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            target_folder = sys.argv[1]

    if len(sys.argv) > 2:
        target_folder = sys.argv[2]

    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), target_folder)
    os.makedirs(target_dir, exist_ok=True)

    print("==================================================")
    print(f"   GENERATING {count} PROCEDURAL TEST IEEE PAPERS ")
    print("==================================================")
    print(f"  Target directory: {target_dir}/")
    print(f"  Dynamic features: Abstract length (40 - 350 words), Author count (1 - 6), Multi-Affiliations\n")

    # Clear old test files if requested
    for f in os.listdir(target_dir):
        if f.startswith("TEST_") and f.endswith(".pdf"):
            try:
                os.remove(os.path.join(target_dir, f))
            except Exception:
                pass

    summary_counts = {'short': 0, 'medium': 0, 'long': 0, 'very_long': 0}

    for i in range(1, count + 1):
        data = generate_random_paper_content(i)
        summary_counts[data['category']] += 1
        filename = os.path.join(target_dir, f"TEST_PAPER_{i:02d}_{data['category'].upper()}.pdf")
        create_ieee_test_pdf(filename, data)
        print(f"  [{i:02d}/{count:02d}] {os.path.basename(filename):<36} -> {data['word_count']:3d} words, {data['title'][:40]}...")

    print(f"\n{'='*60}")
    print(f"[DONE] Successfully generated {count} test PDFs in {target_dir}/")
    print(f"  Distribution: {summary_counts['short']} Short (40-70w), {summary_counts['medium']} Medium (120-180w), {summary_counts['long']} Long (240-290w), {summary_counts['very_long']} Very Long (300-360w)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
