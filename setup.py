from setuptools import find_packages, setup


setup(
	name="auto_payment_reconciliation",
	version="0.0.1",
	description="Supplier-wise automatic payment reconciliation for ERPNext",
	author="Dux Digitech",
	author_email="support@duxdigitech.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
)
