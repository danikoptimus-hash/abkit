// Assembles `<experiment>_<dataset>_<suffix>` download filenames for the two
// client-side blob downloads (export zip, detailed results CSV). Mirror of
// abkit/download_names.py::build_experiment_download_name — sanitization lives
// on the backend; `datasetSegment` here is the already-sanitized value the
// backend exposes on ExperimentDetail.download_dataset_segment. Kept pure (no
// DOM) so it's unit-tested under vitest.
export function experimentDownloadName(
  experimentName: string,
  datasetSegment: string | null | undefined,
  suffix: string,
): string {
  return datasetSegment
    ? `${experimentName}_${datasetSegment}_${suffix}`
    : `${experimentName}_${suffix}`
}
