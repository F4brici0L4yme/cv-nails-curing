## II. RELATED WORK

### A. Ultraviolet Exposure From Nail Curing Devices

Measurements of commercial nail curing devices report differences in spectral irradiance across device models and measurement positions [1]–[3]. These studies support characterizing both the emitted field and the spatial distribution of exposure when evaluating a localized curing system. Their measurements do not, by themselves, establish clinical outcomes for an individual user. Cell-based studies have reported biological responses following exposure to nail polish dryers, but these in vitro findings should not be interpreted as direct evidence of clinical risk from routine salon use [4], [5]. Accordingly, the present work treats limiting illumination outside the nail as an engineering objective to be measured, rather than as a demonstrated clinical benefit.

### B. Nail Segmentation and Robot–Camera Calibration

Nail segmentation is challenging because nail and surrounding skin can have similar appearance. A geometry-based method evaluated on 348 toenail images reported an F-measure of 0.925 on its test set [6]. This result provides methodological context but does not predict performance on fingernails or salon imagery. A separate fingernail segmentation system demonstrates the relevance of learned segmentation for hand images [7]. For a vision-guided manipulator, converting image locations into actuator targets also depends on camera-to-workspace calibration. Comparative robot-world-hand–eye calibration work and a low-cost SCARA visual-servoing study provide relevant methods for planar positioning [8], [9]; neither directly evaluates a nail-curing application.

### C. Optical Measurement and Dosimetry

Ultraviolet measurement guidance emphasizes matching a radiometer to the wavelength band and measurement geometry, and distinguishing relative monitoring from calibrated absolute irradiance [10]. Consequently, an uncalibrated photodiode connected to a microcontroller ADC should be reported as a relative sensor signal rather than an absolute UV dose. The prototype evaluation must specify the emitter spectrum, sensor response, reference instrument, and calibration procedure before reporting irradiance or radiant exposure.

## References

[1] J. Baeza et al., “Nail dryer devices: a measured spectral irradiance and labelling review,” *Photochemical & Photobiological Sciences*, vol. 17, no. 5, pp. 592–598, 2018, doi: 10.1039/C7PP00388A.

[2] C. Ford et al., “Quantifying the ultraviolet radiation emitted by nail curing devices: A descriptive study,” *Australasian Journal of Dermatology*, vol. 62, no. 2, pp. e311–e313, 2021, doi: 10.1111/ajd.13539.

[3] S. Dowdy and R. Sayre, “Photobiological safety evaluation of UV nail lamps,” *Photochemistry and Photobiology*, vol. 89, no. 4, pp. 961–967, 2013, doi: 10.1111/php.12075.

[4] L. R. Shipp, C. A. Warner, F. A. Rueggeberg, and L. S. Davis, “Further investigation into the risk of skin cancer associated with the use of UV nail lamps,” *JAMA Dermatology*, vol. 150, no. 7, pp. 775–776, 2014, doi: 10.1001/jamadermatol.2013.8740.

[5] M. Zhivagui et al., “DNA damage and somatic mutations in mammalian cells after irradiation with a nail polish dryer,” *Nature Communications*, vol. 14, art. 276, 2023, doi: 10.1038/s41467-023-35876-8.

[6] B. Galmés, G. Moyà-Alcover, P. Bibiloni, J. Varona, and A. Jaume-i-Capó, “Geometric-based nail segmentation for clinical measurements,” *Multimedia Tools and Applications*, vol. 81, pp. 16117–16132, 2022, doi: 10.1007/s11042-022-12234-2.

[7] L. Tenze and E. Canessa, “NAILS: Normalized Artificial Intelligence Labeling Sensor for Self-Care Health,” *Sensors*, vol. 24, no. 24, art. 7997, 2024, doi: 10.3390/s24247997.

[8] S. Shah, A. Dhall, and S. Sharma, “Methods for simultaneous robot-world-hand–eye calibration: A comparative study,” *Sensors*, vol. 19, no. 12, art. 2837, 2019, doi: 10.3390/s19122837.

[9] P. Ðurović, R. Grbić, and R. Cupec, “Visual servoing for low-cost SCARA robots using an RGB-D camera as the only sensor,” *Automatika*, vol. 58, no. 4, pp. 495–505, 2017, doi: 10.1080/00051144.2018.1461771.

[10] J. L. M. Farr et al., “Guidelines on the measurement of ultraviolet radiation levels in ultraviolet phototherapy,” *British Journal of Dermatology*, vol. 173, no. 2, pp. 333–350, 2015, doi: 10.1111/bjd.13937.
