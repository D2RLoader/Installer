# Signs one file with a code signing certificate from the Windows certificate store.
# Inno Setup calls this script through the sign tool "d2rloader" (see build.py). It signs Setup and the uninstaller.
param(
	[Parameter(Mandatory = $true)]
	[string]$TargetPath,

	[Parameter(Mandatory = $true)]
	[string]$Thumbprint,

	[string]$TimestampUrl = ""
)

$ErrorActionPreference = "Stop"

$cert = $null
foreach ($location in @("CurrentUser", "LocalMachine")) {
	$store = [Security.Cryptography.X509Certificates.X509Store]::new("My", $location)
	try {
		$store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
		$cert = $store.Certificates.Find([Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $Thumbprint, $false) |
			Where-Object { $_.HasPrivateKey } | Select-Object -First 1
	} finally {
		$store.Close()
	}
	if ($cert) {
		break
	}
}
if (-not $cert) {
	throw "No certificate with a private key and the thumbprint $Thumbprint is in the certificate store."
}

$arguments = @{ FilePath = $TargetPath; Certificate = $cert; HashAlgorithm = "SHA256" }
if ($TimestampUrl) {
	$arguments.TimestampServer = $TimestampUrl
}
$signature = Set-AuthenticodeSignature @arguments
if ($signature.Status.ToString() -ne "Valid") {
	throw "Signing failed for $TargetPath`: $($signature.Status) $($signature.StatusMessage)"
}
Write-Host "Signed $TargetPath"
