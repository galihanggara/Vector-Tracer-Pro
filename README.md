# Vector Tracer Pro

Konversi gambar raster (JPG/PNG) ke SVG siap jual untuk Adobe Stock, 
Shutterstock, dan Freepik.

## Download
[VectorTracerPro-Setup-1.0.0.exe](https://github.com/galihanggara/Vector-Tracer-Pro/releases/download/v1.0.0/VectorTracerPro-Setup-1.0.0.exe)

## Dependensi Opsional
- **Inkscape** (opsional): untuk engine tracing tambahan
  Download: https://inkscape.org/release/

## Build dari Source
```bash
pip install -e .[dev]
python scripts/build.py
```

## Marketplace Validation
| Marketplace  | Min Resolusi | Max Size | Catatan         |
|--------------|-------------|----------|-----------------|
| Adobe Stock  | 15MP        | 100MB    | RGB only        |
| Shutterstock | 4MP         | 50MB     | IPTC recommended|
| Freepik      | -           | 25MB     | SVG/EPS         |
