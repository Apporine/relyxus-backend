$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$out = Join-Path $root "relyxus-deploy.zip"
if (Test-Path $out) { Remove-Item $out -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$skipDirs = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]@(".git", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cursor", "htmlcov", "__pycache__")
)
$zip = [System.IO.Compression.ZipFile]::Open($out, "Create")
try {
    $count = 0
    Get-ChildItem -Path $root -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($root.Length).TrimStart("\")
        $parts = $rel.Split("\")
        foreach ($p in $parts) {
            if ($skipDirs.Contains($p)) { return }
        }
        if ($_.Extension -eq ".pem") { return }
        if ($_.Name -eq "relyxus-deploy.zip") { return }
        $entryName = $rel.Replace("\", "/")
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $_.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal
        )
        $count++
    }
    Write-Output "files=$count bytes=$((Get-Item $out).Length)"
} finally {
    $zip.Dispose()
}
