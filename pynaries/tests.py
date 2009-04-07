import unittest
from version import Version

class VersionTestCase(unittest.TestCase):
	def testFromString(self):
		v = Version.fromObject("1.3.3sp1")
		self.assertEquals(v.major, 1)
		self.assertEquals(v.minor, '3')
		self.assertEquals(v.micro, '3sp1')
		self.assertEquals(Version.getNumericPiece(v.micro), '3')
		self.assertEquals(Version.getAnnotationPiece(v.micro), 'sp1')
		self.assertEquals(str(v), "1.3.3sp1")
	
	def testComparisons(self):
		self.assertTrue(Version.fromObject('1.3.3') < Version.fromObject('1.3.3sp1'))
		self.assertTrue(Version.fromObject('1.4.0') > Version.fromObject('1.3.3sp1'))
		self.assertTrue(Version.fromObject('1.3.3p1') < Version.fromObject('1.4.0'))


if __name__ == '__main__':
	unittest.main()