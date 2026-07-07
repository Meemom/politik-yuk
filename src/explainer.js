export const READING_LEVELS = [
  {
    id: "smp",
    label: "SMP",
    description: "Kalimat pendek, istilah dijelaskan sangat sederhana.",
  },
  {
    id: "sma",
    label: "SMA",
    description: "Tetap ringkas, dengan konteks politik dasar.",
  },
  {
    id: "mahasiswa",
    label: "Mahasiswa",
    description: "Lebih analitis, tetapi tetap jernih dan netral.",
  },
];

export const DEFAULT_READING_LEVEL = "sma";

export function getReadingLevel(id) {
  return (
    READING_LEVELS.find((level) => level.id === id) ??
    READING_LEVELS.find((level) => level.id === DEFAULT_READING_LEVEL)
  );
}

export function buildPlaceholderExplanation(levelId = DEFAULT_READING_LEVEL) {
  const level = getReadingLevel(levelId);

  return [
    {
      title: "Ringkasan Singkat",
      body: `Artikel akan diringkas untuk tingkat ${level.label} dalam 3 sampai 5 kalimat utama.`,
    },
    {
      title: "Penjelasan Sederhana",
      body: "Bagian ini akan menjelaskan inti peristiwa dengan bahasa yang lebih mudah, tanpa menambah fakta di luar artikel.",
    },
    {
      title: "Tokoh dan Lembaga Penting",
      body: "Nama tokoh, partai, kementerian, atau lembaga akan dijelaskan sesuai perannya di artikel.",
    },
    {
      title: "Istilah Sulit",
      body: "Istilah politik, hukum, atau pemerintahan akan diterjemahkan menjadi definisi singkat.",
    },
    {
      title: "Kenapa Ini Penting",
      body: "Bagian ini akan membantu pembaca memahami dampak sosial atau kewargaan dari berita.",
    },
    {
      title: "Dampak ke Kehidupan Sehari-hari",
      body: "Kemungkinan dampak praktis akan dijelaskan dengan hati-hati dan tidak dilebih-lebihkan.",
    },
    {
      title: "Pertanyaan Kritis",
      body: "Aplikasi akan memberi beberapa pertanyaan untuk membantu pembaca berpikir lebih kritis.",
    },
    {
      title: "Hal yang Perlu Dicek Lagi",
      body: "Klaim, angka, tuduhan, atau prediksi yang belum jelas akan ditandai agar tidak langsung dipercaya.",
    },
  ];
}

export function validateArticleText(text) {
  const trimmedText = text.trim();

  if (trimmedText.length === 0) {
    return "Tempel artikel terlebih dahulu.";
  }

  if (trimmedText.length < 300) {
    return "Artikel terlalu pendek. Tempel setidaknya 300 karakter agar konteksnya cukup.";
  }

  if (trimmedText.length > 20000) {
    return "Artikel terlalu panjang. Gunakan maksimal 20.000 karakter untuk MVP ini.";
  }

  return "";
}
