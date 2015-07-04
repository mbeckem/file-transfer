var sizeUnits = {
  iec: ["KiB", "MiB", "GiB", "TiB", "PiB"],
  si: ["KB", "MB", "GB", "TB", "PB"],
};

// Formats the given size in bytes as a human readable string (including units).
// useIEC: Use binary-based units instead of SI units (e.g. KiB instead of KB). Defaults to false.
export default function fileSize(size, useIEC) {
  useIEC = !!useIEC;

  var base = useIEC ? 1024 : 1000;
  var idx = (Math.log(size) / Math.log(base)) | 0;
  if (idx >= sizeUnits.si.length) {
    idx = sizeUnits.si.length - 1;
  }

  if (idx === 0) {
    return (size | 0) + " Bytes";
  }
  return (size / Math.pow(base, idx)).toFixed(2) + " " + (useIEC ? sizeUnits.iec : sizeUnits.si)[idx - 1];
}
