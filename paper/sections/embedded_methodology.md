## III. SYSTEM DESIGN AND EMBEDDED CONTROL

### A. Mechatronic Architecture

The prototype is organized into a host-side vision and command application and an embedded actuation unit. The host estimates a nail target and sends joint targets and a curing duration to an ESP32 DevKit V1 over a 115200-baud UART connection. The ESP32 commands two hobby servos in a nominal planar, two-degree-of-freedom arrangement and switches a UV LED through a MOSFET. A plano-convex lens is mounted in the emitter optical path. An optional UV photodiode is connected to an ADC input for optical monitoring. The hand is assumed to remain stationary on a calibrated plane during a curing cycle.

The electrical design separates the servo supply from the ESP32 logic supply. Servos are powered by an external regulated 5–6 V source, with its ground connected to ESP32 ground; the ESP32 GPIO pins provide control signals only. The UV emitter is powered according to its rated current and thermal requirements and is switched by a logic-level MOSFET. Its current-limiting or constant-current circuit must be selected for the actual emitter; it is not specified by the current prototype description. GPIO 23 controls the MOSFET gate, GPIO 18 and GPIO 19 provide the servo control signals, and GPIO 34 is reserved for the optional analog sensor. These pin and supply assignments describe the prototype interface and require confirmation against the assembled hardware.

### B. Kinematic Mapping and Calibration

For a planar two-link model with link lengths $L_1$ and $L_2$, the forward kinematics of a target point $(x,y)$ are
\[
x=L_1\cos\theta_1+L_2\cos(\theta_1+\theta_2),\qquad
y=L_1\sin\theta_1+L_2\sin(\theta_1+\theta_2).
\]
The corresponding inverse-kinematics relation is
\[
\cos\theta_2=\frac{x^2+y^2-L_1^2-L_2^2}{2L_1L_2},\qquad
\theta_1=\operatorname{atan2}(y,x)-\operatorname{atan2}\bigl(L_2\sin\theta_2,L_1+L_2\cos\theta_2\bigr).
\]
The inverse solution has two possible elbow configurations when the target is reachable. The selected branch must agree with the physical assembly and servo limits. Link lengths, origin offset, usable workspace, servo pulse calibration, and joint limits remain to be measured and agreed with the vision subsystem. A planar camera-to-workspace mapping and mechanical zero offsets are to be established using the calibration procedure before reporting end-to-end positioning accuracy. No positioning accuracy is claimed in this draft.

### C. Embedded Command and Safety Logic

The host-to-controller interface uses newline-delimited JSON. A `CURE` command contains `nail_id`, `theta1`, `theta2`, and `duration_ms`; an `ABORT` command requests termination of an active cure. The documented completion message contains status, nail identifier, elapsed curing time, average ADC reading, and a skin-spill estimate. The meaning and calibration of the last two sensor-derived values must be finalized with the host implementation; until validated, ADC values are raw or relative measurements and a spill estimate must not be described as measured irradiance.

The intended firmware is a non-blocking finite-state machine with `IDLE`, `MOVING`, `CURING`, `COMPLETE`, and `ERROR` states. A cycle begins with UV disabled, moves the servos to the requested target, and permits UV activation only after motion is complete. During curing, the controller tracks elapsed time and samples the optional ADC input. Completion, an abort request, or reaching `MAX_CURE_MS` (specified as 15000 ms) returns the UV output to LOW. Serial disconnection behavior and the response to malformed or out-of-range commands must be implemented and tested before the device is used; the present interface description does not establish measured response times or a separate hardware cutoff. The watchdog refers to firmware timeout logic and must not be represented as an independent safety circuit.

### D. Experimental Measures

The hardware evaluation should report mean and standard deviation across repeated trials. Suggested measures are: (1) Cartesian pointing error in millimeters, measured between the commanded nail target and observed emitter spot; (2) command-to-cure latency in milliseconds, measured from host transmission to the onset of optical emission; (3) curing-time error, comparing requested duration with an independent time reference; and (4) optical readings at the nail target and adjacent skin locations. Absolute irradiance or radiant exposure should be reported only if the sensor and measurement geometry are calibrated against a suitable reference instrument. Trial count, gel formulation, emitter wavelength, sensor calibration, workspace, and hand position are pending experimental specification. No quantitative performance result is available yet.
