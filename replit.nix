{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.chromedriver
    pkgs.geckodriver
    pkgs.postgresql
    pkgs.openssl
  ];
}
