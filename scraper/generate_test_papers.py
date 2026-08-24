#!/usr/bin/env python3
"""
Generate diverse IEEE-formatted test PDF papers with different sizes:
- Small (~180pt)
- Medium (~310pt)
- Borderline Large A (~370pt)
- Borderline Large B (~375pt)
- Large Single-Page (~480pt)
- Small Compact B (~190pt)

Used to thoroughly test dynamic sizing, adaptive margin squeeze, and multi-fit page packing.
"""

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

def create_ieee_test_pdf(filename, title, authors, affiliations, abstract, keywords):
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
        Paragraph(title, st_title),
        Paragraph(authors, st_auth),
    ]
    if affiliations:
        story.append(Paragraph(affiliations, st_aff))

    story.extend([
        Paragraph(f"<b>Abstract— </b>{abstract}", st_abs),
        Paragraph(f"<b>Keywords— </b><i>{keywords}</i>", st_kw),
        Spacer(1, 10),
        Paragraph("<b>I. INTRODUCTION</b>", ParagraphStyle('H1', fontName='Times-Bold', fontSize=10, leading=13)),
        Paragraph("With recent advancements in distributed computing and edge intelligent systems, modern telemetry architectures demand highly resilient, latency-sensitive pipelines that guarantee throughput under stringent bandwidth constraints.", st_body),
        Paragraph("This study analyzes the performance benchmarks, empirical verifications, and architectural trade-offs observed during experimental trials.", st_body)
    ])

    doc.build(story)
    print(f"  [CREATED] {os.path.basename(filename)}")


def main():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IncompletePDF")
    os.makedirs(target_dir, exist_ok=True)

    print("==================================================")
    print("      GENERATING DIVERSE SIZED TEST PAPERS        ")
    print("==================================================")

    # 1. SMALL PAPER (~180pt: 1 author, short abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_01_Small.pdf"),
        title="Micro-Telemetry Protocols for Embedded IoT Nodes",
        authors="Aarav Sharma",
        affiliations="Department of Computer Engineering, IIT Bombay, Maharashtra, India",
        abstract="This paper introduces a low-power micro-telemetry protocol optimized for constrained embedded sensor arrays in remote agricultural monitoring environments.",
        keywords="IoT Nodes, Embedded Systems, Micro-Telemetry, Low Power Wireless"
    )

    # 2. MEDIUM PAPER (~310pt: 3 authors, 2 affiliations, standard abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_02_Medium.pdf"),
        title="Neural Beamforming Architectures for 6G Satellite Communications",
        authors="Tejaswi Palisetti, Suresh Jain, Kailash Chandra",
        affiliations="Department of Electronics and Communication Engineering, Amrita School of Engineering, Tamil Nadu, India",
        abstract="Next-generation satellite mega-constellations necessitate adaptive beamforming architectures that dynamically respond to fast channel variations and orbital Doppler shifts. We propose a deep reinforcement learning framework that synthesizes multi-beam radiation patterns in real-time, achieving up to 34% reduction in inter-beam interference while maintaining strict signal-to-noise thresholds across millimeter-wave uplinks.",
        keywords="Beamforming, 6G Satellites, Deep Reinforcement Learning, Millimeter Wave, Interference Cancellation"
    )

    # 3. BORDERLINE LARGE A (~370pt: 4 authors, multi-line title, long abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_03_Borderline_LargeA.pdf"),
        title="Fault-Tolerant Federated Learning over Heterogeneous Edge Clusters with Dynamic Gradient Compression",
        authors="Garima Mathur, Siddharth Singh Parihar, Vivek Kumar Gupta, Rashmi Jangid",
        affiliations="Dept. of Computer Science & Engineering, Sagar Institute of Science and Technology, Bhopal, Madhya Pradesh, India",
        abstract="Federated edge learning enables decentralized model training across distributed edge computing nodes without centralized data ingestion. However, straggler nodes and communication bottlenecks frequently degrade convergence rates in real-world deployments. In this work, we design a fault-tolerant optimization framework combining quantized gradient compression with localized momentum caching. Comprehensive empirical simulations demonstrate a 2.4x speedup in wall-clock training time across non-IID datasets without compromising test accuracy or cryptographic gradient privacy.",
        keywords="Federated Learning, Edge Computing, Gradient Compression, Fault Tolerance, Decentralized AI, Privacy Preservation"
    )

    # 4. BORDERLINE LARGE B (~375pt: 5 authors, multi-line title, extensive abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_04_Borderline_LargeB.pdf"),
        title="Autonomous Threat Detection in Industrial Cyber-Physical Systems via Graph Neural Network Ensembles",
        authors="Tapan Nahar, Arpit Kumar Sharma, Praveen Kumar Sharma, Mitesh Solanki, Sanyog Rawat",
        affiliations="Department of Information and Communication Technology, Manipal University Jaipur, Rajasthan, India",
        abstract="Industrial Cyber-Physical Systems (ICPS) are increasingly targeted by sophisticated multi-stage cyber threats that exploit subtle physical process correlations. Traditional signature-based intrusion detection systems fail to detect zero-day coordinated sensor-spoofing anomalies. We present an end-to-end temporal graph neural network ensemble that models spatial topological dependencies alongside high-frequency sensor telemetry. Extensive evaluations across benchmark water treatment and power grid datasets indicate detection precision exceeding 98.6% with sub-second response latency.",
        keywords="Cyber-Physical Systems, Industrial IoT, Graph Neural Networks, Intrusion Detection, Anomaly Detection, Zero-Day Exploits"
    )

    # 5. LARGE SINGLE PAGE (~480pt: 6 authors, multiple institutions, very large abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_05_Large_SinglePage.pdf"),
        title="Comprehensive Benchmarking of Transformer and Diffusion Architectures for Real-Time Multimodal Medical Image Synthesis and Diagnostic Reconstruction",
        authors="Dr. Rajeshwari Swaminathan, Dr. Vikramaditya Sen, Prof. Ananya Roy, Dr. Meenakshi Sundaram, Dr. Alok Nath, Dr. Sunita Deshmukh",
        affiliations="Center for Computational Biology and Medical Imaging, All India Institute of Medical Sciences, New Delhi, India",
        abstract="Medical imaging modalities such as high-resolution MRI, Contrast-Enhanced CT, and Positron Emission Tomography often suffer from acquisition artifacts, radiation dose limitations, and scanning duration constraints. Recent breakthroughs in generative diffusion models and vision transformers present unprecedented opportunities for cross-modal synthesis, super-resolution reconstruction, and artifact suppression. In this extensive study, we present a standardized multi-center benchmark comparing eleven state-of-the-art vision architectures across four major clinical datasets comprising over 50,000 volumetric scans. We quantify reconstruction fidelity using Structural Similarity Index (SSIM), Peak Signal-to-Noise Ratio (PSNR), and downstream clinical diagnostic accuracy evaluated blindly by twenty board-certified radiologists. Our findings establish critical guidelines for deploying generative imaging models in latency-critical emergency room workflows.",
        keywords="Medical Image Synthesis, Vision Transformers, Generative Diffusion Models, Multi-Modal Reconstruction, MRI Super-Resolution, Radiologist Evaluation"
    )

    # 6. SMALL COMPACT B (~190pt: 2 authors, short abstract)
    create_ieee_test_pdf(
        os.path.join(target_dir, "TEST_06_Small_CompactB.pdf"),
        title="Quantum-Resistant Key Exchange for Smart Grid Metering",
        authors="Priyanka Singh, Shweta Singh",
        affiliations="Dept. of Computer Science & Engineering, Oriental College of Technology, Bhopal, Madhya Pradesh, India",
        abstract="Smart grid smart meters require lightweight post-quantum key encapsulation mechanisms to secure continuous consumption telemetry against future cryptanalytic attacks.",
        keywords="Post-Quantum Cryptography, Smart Grid, Key Encapsulation, Lattice-Based Cryptography"
    )

    print(f"\n[DONE] Successfully generated 6 test PDFs in {target_dir}/")

if __name__ == "__main__":
    main()
