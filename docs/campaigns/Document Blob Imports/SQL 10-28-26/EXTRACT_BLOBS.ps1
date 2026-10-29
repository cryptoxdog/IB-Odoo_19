# Windows PowerShell 5.1 only. Do not paste this into SSMS. Use a new PowerShell window.
# Live UCSerp. Saves every erp_SM original through ImageID 721202. No database backup.
# Odoo import later uses ImportScope=eligible only (RefType W and #).
# P is archive_only. E and B are unattached. Those files are still extracted.
# Full run. Resumes after the last ImageID already in journal.csv. $Limit = 0 means no cap.

$ErrorActionPreference = 'Stop'
$Limit = 0
$MaxImageId = 721202
$OutRoot = '\\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\extract'

New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot 'raw') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot 'decoded') | Out-Null
Get-ChildItem -Path $OutRoot -Recurse -Filter '*.partial' -ErrorAction SilentlyContinue | Remove-Item -Force

$Journal = Join-Path $OutRoot 'journal.csv'
$Header = 'ImageID,DocID,RefID,RefType,FileExt,BlobSize,CreatedDT,RawBytes,RawSha256,DecodedBytes,DecodedSha256,Status,ImportScope'
if (-not (Test-Path -LiteralPath $Journal)) {
    $Header | Set-Content -LiteralPath $Journal -Encoding ASCII
} else {
    $existing = @(Get-Content -LiteralPath $Journal)
    if ($existing.Count -gt 0 -and $existing[0] -notmatch 'ImportScope') {
        $upgraded = New-Object System.Collections.Generic.List[string]
        $upgraded.Add($Header)
        foreach ($line in $existing) {
            if (-not $line -or $line -eq $existing[0]) { continue }
            $parts = $line.Split(',')
            $refType = ''
            if ($parts.Length -gt 3) { $refType = $parts[3].Trim('"') }
            $scope = 'archive_only'
            if ($refType -eq 'W' -or $refType -eq '#') { $scope = 'eligible' }
            elseif ($refType -eq 'E' -or $refType -eq 'B') { $scope = 'unattached' }
            $upgraded.Add($line + ',' + $scope)
        }
        [System.IO.File]::WriteAllLines($Journal, $upgraded.ToArray())
    }
}

$Last = 0
Get-Content -LiteralPath $Journal | Select-Object -Skip 1 | ForEach-Object {
    if ($_ -match '^(\d+),') {
        $n = [int]$Matches[1]
        if ($n -gt $Last) { $Last = $n }
    }
}
Write-Host "RESUME_AFTER $Last LIMIT $Limit"

if (-not ('erp.BlobExtractV2' -as [type])) {
    Add-Type -ReferencedAssemblies @('System.Data', 'System.IO.Compression') -TypeDefinition @'
using System;
using System.Data;
using System.Data.SqlClient;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

namespace erp
{
    public static class BlobExtractV2
    {
        const long MaxBytes = 40L * 1024L * 1024L;

        public static void Run(string outRoot, int afterId, int maxImageId, int limit)
        {
            string rawDir = Path.Combine(outRoot, "raw");
            string decDir = Path.Combine(outRoot, "decoded");
            string journal = Path.Combine(outRoot, "journal.csv");
            string cs = "Server=UCSerp;Database=erp_Documents;Integrated Security=True;Packet Size=32767;Connect Timeout=60;";
            string top = limit > 0 ? "TOP (@limit) " : "";
            string sql = "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED; SELECT " + top
                + "ImageID, DocID, "
                + "LTRIM(RTRIM(CONVERT(varchar(255), RefID))) AS RefID, "
                + "LTRIM(RTRIM(CONVERT(varchar(20), RefType))) AS RefType, "
                + "LTRIM(RTRIM(CONVERT(varchar(20), FileExt))) AS FileExt, "
                + "Blob_Size, CONVERT(varchar(23), CreatedDT, 121) AS CreatedDT, Blob_Image "
                + "FROM dbo.DocumentImage "
                + "WHERE ImageID > @after AND ImageID <= @maxId "
                + "AND UPPER(RTRIM(CONVERT(varchar(128), DBName))) = 'erp_SM' "
                + "ORDER BY ImageID";

            int written = 0;
            int ok = 0;
            using (SqlConnection conn = new SqlConnection(cs))
            {
                conn.Open();
                using (SqlCommand cmd = new SqlCommand(sql, conn))
                {
                    cmd.CommandTimeout = 0;
                    cmd.Parameters.Add("@after", SqlDbType.Int).Value = afterId;
                    cmd.Parameters.Add("@maxId", SqlDbType.Int).Value = maxImageId;
                    if (limit > 0)
                    {
                        cmd.Parameters.Add("@limit", SqlDbType.Int).Value = limit;
                    }
                    using (SqlDataReader reader = cmd.ExecuteReader(CommandBehavior.SequentialAccess))
                    using (StreamWriter log = new StreamWriter(journal, true, new UTF8Encoding(false)))
                    {
                        log.AutoFlush = true;
                        byte[] buffer = new byte[1024 * 256];
                        while (reader.Read())
                        {
                            int imageId = reader.GetInt32(0);
                            int docId = reader.GetInt32(1);
                            string refId = reader.IsDBNull(2) ? "" : reader.GetString(2);
                            string refType = reader.IsDBNull(3) ? "" : reader.GetString(3);
                            string fileExt = reader.IsDBNull(4) ? "" : reader.GetString(4);
                            double blobSize = reader.IsDBNull(5) ? 0d : reader.GetDouble(5);
                            string created = reader.IsDBNull(6) ? "" : reader.GetString(6);
                            string status = "ok";
                            long rawBytes = 0;
                            string rawSha = "";
                            long decodedBytes = 0;
                            string decodedSha = "";
                            string rawPath = Path.Combine(rawDir, imageId.ToString() + ".bin");
                            string rawPartial = rawPath + ".partial";
                            try
                            {
                                if (reader.IsDBNull(7))
                                {
                                    status = "empty";
                                }
                                else
                                {
                                    using (SHA256 sha = SHA256.Create())
                                    using (FileStream fs = new FileStream(rawPartial, FileMode.Create, FileAccess.Write, FileShare.None))
                                    {
                                        long offset = 0;
                                        while (true)
                                        {
                                            long n = reader.GetBytes(7, offset, buffer, 0, buffer.Length);
                                            if (n <= 0) break;
                                            if (offset + n > MaxBytes) throw new InvalidOperationException("raw cap");
                                            sha.TransformBlock(buffer, 0, (int)n, null, 0);
                                            fs.Write(buffer, 0, (int)n);
                                            offset += n;
                                        }
                                        sha.TransformFinalBlock(new byte[0], 0, 0);
                                        rawBytes = offset;
                                        rawSha = Hex(sha.Hash);
                                    }
                                    if (File.Exists(rawPath)) File.Delete(rawPath);
                                    File.Move(rawPartial, rawPath);
                                    if (rawBytes == 0)
                                    {
                                        status = "empty";
                                    }
                                    else if (!IsGzip(rawPath))
                                    {
                                        status = "not_gzip";
                                    }
                                    else
                                    {
                                        string ext = SafeExt(fileExt);
                                        string decPath = Path.Combine(decDir, imageId.ToString() + "." + ext);
                                        string decPartial = decPath + ".partial";
                                        try
                                        {
                                            decodedSha = Decode(rawPath, decPartial, out decodedBytes);
                                            if (File.Exists(decPath)) File.Delete(decPath);
                                            File.Move(decPartial, decPath);
                                            long expect = (long)Math.Round(blobSize);
                                            if (decodedBytes != expect) status = "length_mismatch";
                                        }
                                        catch (Exception)
                                        {
                                            status = "decode_failed";
                                            if (File.Exists(decPartial)) File.Delete(decPartial);
                                        }
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                Console.WriteLine("FAIL " + imageId.ToString() + " " + ex.Message);
                                if (File.Exists(rawPartial)) File.Delete(rawPartial);
                                throw;
                            }
                            log.WriteLine(string.Join(",",
                                imageId.ToString(),
                                docId.ToString(),
                                Q(refId),
                                Q(refType),
                                Q(fileExt),
                                blobSize.ToString("0"),
                                Q(created),
                                rawBytes.ToString(),
                                rawSha,
                                decodedBytes.ToString(),
                                decodedSha,
                                status,
                                ImportScope(refType)));
                            written++;
                            if (status == "ok") ok++;
                            Console.WriteLine(imageId.ToString() + " " + status + " raw=" + rawBytes.ToString() + " sha=" + rawSha);
                        }
                    }
                }
            }
            Console.WriteLine("DONE written=" + written.ToString() + " ok=" + ok.ToString());
        }

        static bool IsGzip(string path)
        {
            using (FileStream fs = File.OpenRead(path))
            {
                int a = fs.ReadByte();
                int b = fs.ReadByte();
                return a == 0x1F && b == 0x8B;
            }
        }

        static string Decode(string rawPath, string decPartial, out long total)
        {
            total = 0;
            using (SHA256 sha = SHA256.Create())
            using (FileStream input = File.OpenRead(rawPath))
            using (GZipStream gzip = new GZipStream(input, CompressionMode.Decompress))
            using (FileStream output = new FileStream(decPartial, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                byte[] buffer = new byte[1024 * 256];
                int n;
                while ((n = gzip.Read(buffer, 0, buffer.Length)) > 0)
                {
                    total += n;
                    if (total > MaxBytes) throw new InvalidOperationException("decoded cap");
                    sha.TransformBlock(buffer, 0, n, null, 0);
                    output.Write(buffer, 0, n);
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return Hex(sha.Hash);
            }
        }

        static string SafeExt(string fileExt)
        {
            if (fileExt == null) return "bin";
            string ext = fileExt.Trim();
            while (ext.StartsWith(".")) ext = ext.Substring(1);
            if (ext.Length == 0 || ext.Length > 8) return "bin";
            for (int i = 0; i < ext.Length; i++)
            {
                if (!char.IsLetterOrDigit(ext[i])) return "bin";
            }
            return ext;
        }

        static string Hex(byte[] hash)
        {
            StringBuilder sb = new StringBuilder(hash.Length * 2);
            for (int i = 0; i < hash.Length; i++) sb.Append(hash[i].ToString("x2"));
            return sb.ToString();
        }

        static string ImportScope(string refType)
        {
            if (refType == "W" || refType == "#") return "eligible";
            if (refType == "E" || refType == "B") return "unattached";
            return "archive_only";
        }

        static string Q(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            if (value.IndexOf(',') >= 0 || value.IndexOf('"') >= 0)
            {
                return "\"" + value.Replace("\"", "\"\"") + "\"";
            }
            return value;
        }
    }
}
'@
}

[erp.BlobExtractV2]::Run($OutRoot, $Last, $MaxImageId, $Limit)
Write-Host "JOURNAL $Journal"
