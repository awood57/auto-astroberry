---
name: astroberry-observing
description: Plan and supervise telescope imaging through Astroberry and KStars/Ekos MCP. Use for rig readiness, manual focus, lunar and planetary bursts, deep-sky lights, flats, darks, dark-flats and verified Siril handoff.
---

## Operate the rig through MCP

Read `observatory_setup`, discover the live tools and inspect `ekos_status`, `mount_coords`, `capture_status` and `capture_get_jobs`. Use the configured profile, train and Pi directories. In read-only mode, inspect and plan. If offline, identify the checks that need a connection.

Confirm site and clock privately, hand-controller alignment, tracking, sky conditions, altitude limits and physical clearance for the whole run. For the stock alt-az mount, inspect short unguided test exposures for drift, trailing and field rotation. If the telescope is at an open doorway, suggest moving it fully outdoors and letting the Mak approach ambient temperature before judging focus or seeing.

Use the operator's agreed target, framing, exposures or burst lengths, count, end time and finish actions. Preserve any active queue. Carry out supported pointing, test exposures, capture and monitoring through MCP. For FITS jobs, load a prepared Ekos sequence under the configured plan directory with `capture_load_sequence` and inspect the jobs before `capture_start`. Follow the rig's commissioned capabilities for focusing, guiding and parking.

For manual focus, center a suitable reference through MCP. Ask the operator to turn the focus knob in small steps. Compare the same feature after each adjustment with a fresh saved test and `image_last_thumbnail`. Use HFR on the same unsaturated star when available. On a planet or lunar field, compare belts, ring tips or crater rims over several previews to distinguish a focus change from momentary seeing. If the field shows only noise or a broad gradient, reacquire the target. Keep the best focus fixed for the burst. Recheck after optics or temperature changes.

## Capture the Moon and planets

Use these starting points for the NexStar 127SLT and SC715C. Adjust exposure and gain from the saved test frame. Inspect the linear histogram for clipped highlights and verify the disk or lunar patch stays inside the frame. A smaller region of interest can improve the Pi's saved frame rate. Leave enough margin for measured drift.

| Target | Starting capture | What to check |
| --- | --- | --- |
| Jupiter | 15 ms, three 60–90 s bursts | Focus on a belt edge. Aim for a few thousand saved frames per burst when measured throughput permits. Keep the bursts separate for quality selection. |
| Saturn | 25 ms, short test recording followed by several 60–90 s bursts | Focus on the ring tips. Verify the test recording closes and reopens with a visible disk and both ring extensions before committing to longer bursts. Keep different gains separate. |
| Moon | 5 ms, 30–60 s on the same patch | Focus on small craters near the terminator and check the brightest rims for clipping. Keep the framing and focus fixed throughout each burst. |

The shipped bridge exposes Ekos sequence controls. Use SER recording only when a connected MCP tool explicitly supports starting and finalizing video. Otherwise use finite raw FITS jobs and measure their saved cadence before choosing a feasible count. If an actual SER is requested and no recorder is exposed, report that capability gap.

After the first burst, verify the saved path, dimensions, Bayer pattern, exposure and actual frame count using available file access. For SER, compare the finalized header and complete pixel payload and inspect frames near the beginning and end. Exclude incomplete frames, preserve the original and flag a header/payload mismatch. For FITS, count readable frames with the expected dimensions. Compare saved frames per elapsed second with the test rate and check remaining storage before repeating. Keep the verification pending when the bridge supplies only status or a thumbnail.

## Capture deep-sky lights and calibration frames

For NGC 1907 on this rig, start with 2 s unguided lights. The prior run used full-frame GRBG, 1×1 binning, gain 260 and offset 0. Verify the active settings from a saved raw. Aim for 15–30 minutes of usable integration when the observing window allows (450–900 accepted 2 s frames). Budget readout and storage from a test batch. Check framing and star shapes between batches and recenter as needed to retain coverage at the edges.

1. **Darks.** Match the lights' exposure, gain, offset, binning, readout mode and sensor region at a similar sensor temperature. Verify headers and dimensions before reusing a master. For the prior 2 s gain-260 lights, use the 12 matched darks or their master. Keep the gain-100 and unrelated darks separate.
2. **Flats.** Before changing focus, camera rotation, filters or the diagonal, ask the operator to place an evenly illuminated diffuser or flat panel over the aperture, or use uniform twilight. Keep the science gain, offset, binning and sensor region. Through MCP, take a raw test flat and adjust exposure toward midrange on the linear histogram. Check each Bayer channel for clipping and inspect for uneven illumination or banding. Capture about 30 undebayered FITS flats. Later flats require a matching optical configuration and dust pattern.
3. **Dark-flats.** Have the operator cover the aperture, or use a commissioned remote cover and verify its state. Capture about 30 capped frames with the exact flat exposure and camera settings at a similar temperature. If flat exposures changed during twilight, group them with matching dark-flats. Keep calibration and light jobs in distinct output groups. Verify the optical path is clear before resuming lights.
4. **Siril handoff.** When processing is requested, use Siril MCP if connected. Subtract the master dark-flat from the raw flats and stack the calibrated flats with multiplicative normalization. Subtract the matched, unscaled master dark from the raw lights and divide by the normalized master flat before debayering, star registration and rejection stacking. Both matched dark masters already include the bias pedestal. Omit separate bias subtraction in this workflow. Use darks or flats on lunar and planetary data only when matched and relevant to the observed defect.

## Close the session

Monitor finite runs through completion or interruption. Verify the agreed capture and tracking end states. Report saved paths, actual counts, accepted counts when measured, integration, rejected or missing frames, calibration matches and observed quality. Distinguish the exposure recorded on disk from the integration retained in the final stack.
